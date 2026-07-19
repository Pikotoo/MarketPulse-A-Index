"""
API Key 管理 CLI

用法:
  py -3.11 scripts/manage_keys.py create --email=admin@example.com --tier=pro --name="张三"
  py -3.11 scripts/manage_keys.py list
  py -3.11 scripts/manage_keys.py disable 1
  py -3.11 scripts/manage_keys.py enable 1
  py -3.11 scripts/manage_keys.py delete 1
  py -3.11 scripts/manage_keys.py stats
"""

import sys
import argparse
from pathlib import Path

# 确保项目根目录在 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.auth import init_db, create_key, list_keys, disable_key, enable_key, delete_key
from config import DB_PATH


def cmd_create(args):
    """创建新 API Key"""
    key = create_key(email=args.email, tier=args.tier, name=args.name)
    print(f"\n✅ API Key 创建成功！")
    print(f"   Key:  {key}")
    print(f"   层级: {args.tier}")
    print(f"   邮箱: {args.email or '(未填写)'}")
    if args.name:
        print(f"   姓名: {args.name}")
    print()
    print(f"   使用示例:")
    print(f'   curl -H "X-API-Key: {key}" http://localhost:8898/api/v1/signal/pe-percentile')
    print()


def cmd_list(args):
    """列出所有 Key"""
    keys = list_keys()
    if not keys:
        print("\n📭 暂无 API Key，请先创建。")
        return

    print(f"\n📋 API Key 列表 ({len(keys)} 个):")
    print(f"{'ID':<4} {'Key Hash':<16} {'层级':<12} {'状态':<8} {'邮箱':<25} {'创建时间'}")
    print("-" * 90)
    for k in keys:
        key_hash_short = k["key_hash"][:14] + ".."
        status = "🟢" if k["status"] == "active" else "🔴"
        print(f"{k['id']:<4} {key_hash_short:<16} {k['tier']:<12} {status:<8} {k['email'] or '—':<25} {k['created_at']}")
    print()


def cmd_disable(args):
    """禁用 Key"""
    disable_key(args.id)
    print(f"✅ Key #{args.id} 已禁用")


def cmd_enable(args):
    """启用 Key"""
    enable_key(args.id)
    print(f"✅ Key #{args.id} 已启用")


def cmd_delete(args):
    """删除 Key"""
    confirm = input(f"⚠️ 确认删除 Key #{args.id}？(y/N): ")
    if confirm.lower() == "y":
        delete_key(args.id)
        print(f"✅ Key #{args.id} 已删除")
    else:
        print("❌ 已取消")


def cmd_stats(args):
    """显示统计信息"""
    print(f"\n📊 MarketPulse 统计")
    print(f"   数据库: {DB_PATH}")
    print(f"   大小: {DB_PATH.stat().st_size / 1024:.1f} KB" if DB_PATH.exists() else "   数据库: 未初始化")
    keys = list_keys()
    active = [k for k in keys if k["status"] == "active"]
    tiers = {}
    for k in active:
        tiers[k["tier"]] = tiers.get(k["tier"], 0) + 1
    print(f"   活跃 Key: {len(active)} 个")
    for tier, count in tiers.items():
        print(f"     {tier}: {count}")
    print()


def main():
    parser = argparse.ArgumentParser(description="MarketPulse API Key 管理")
    subparsers = parser.add_subparsers(dest="command", help="操作")

    # create
    p_create = subparsers.add_parser("create", help="创建新 Key")
    p_create.add_argument("--email", default="", help="用户邮箱")
    p_create.add_argument("--tier", default="free",
                        choices=["free", "personal", "pro", "enterprise"],
                        help="层级 (默认: free)")
    p_create.add_argument("--name", default="", help="用户姓名")

    # list
    p_list = subparsers.add_parser("list", help="列出所有 Key")

    # disable
    p_disable = subparsers.add_parser("disable", help="禁用 Key")
    p_disable.add_argument("id", type=int, help="Key ID")

    # enable
    p_enable = subparsers.add_parser("enable", help="启用 Key")
    p_enable.add_argument("id", type=int, help="Key ID")

    # delete
    p_delete = subparsers.add_parser("delete", help="删除 Key")
    p_delete.add_argument("id", type=int, help="Key ID")

    # stats
    p_stats = subparsers.add_parser("stats", help="统计信息")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    init_db()

    commands = {
        "create": cmd_create,
        "list": cmd_list,
        "disable": cmd_disable,
        "enable": cmd_enable,
        "delete": cmd_delete,
        "stats": cmd_stats,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
