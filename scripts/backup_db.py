"""
每日数据库备份脚本

备份 marketpulse.db 到 backups/db/ 目录，保留最近 30 天。

用法:
  py -3.11 scripts/backup_db.py
  py -3.11 scripts/backup_db.py --cleanup  清理超过30天的旧备份

调度: 每天 3:00 执行一次
"""

import shutil
import sys
from pathlib import Path
from datetime import date, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "marketpulse.db"
BACKUP_ROOT = PROJECT_ROOT / "backups" / "db"
KEEP_DAYS = 30


def backup():
    """执行备份"""
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        sys.exit(1)

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    backup_name = f"marketpulse-{today}.db"
    backup_path = BACKUP_ROOT / backup_name

    # 今天已经备份过则跳过
    if backup_path.exists():
        print(f"⏭️  今日已备份: {backup_name}")
        return

    shutil.copy2(DB_PATH, backup_path)
    size_kb = backup_path.stat().st_size / 1024
    print(f"✅ 备份成功: {backup_name} ({size_kb:.0f} KB)")


def cleanup():
    """清理过期备份"""
    if not BACKUP_ROOT.exists():
        return

    cutoff = date.today() - timedelta(days=KEEP_DAYS)
    deleted = 0
    for f in BACKUP_ROOT.glob("marketpulse-*.db"):
        try:
            d = date.fromisoformat(f.stem.replace("marketpulse-", ""))
            if d < cutoff:
                f.unlink()
                deleted += 1
        except (ValueError, OSError):
            pass

    if deleted:
        print(f"🗑️  清理了 {deleted} 个过期备份")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="MarketPulse DB 备份")
    p.add_argument("--cleanup", action="store_true", help="清理过期备份")
    args = p.parse_args()

    if args.cleanup:
        cleanup()
    else:
        backup()
        cleanup()  # 每次备份后自动清理
