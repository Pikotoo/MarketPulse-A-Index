"""
数据新鲜度检查 — 通过 health API 检查各数据源是否过期

用法:
  py -3.11 scripts/check_freshness.py              # 检查并打印
  py -3.11 scripts/check_freshness.py --alert      # 检查 + 过期时飞书告警
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import urllib.request

_MP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_MP_ROOT))

from config import HEALTH_ENDPOINT_URL

# 过期阈值
THRESHOLDS = {
    "PE":   {"max_days": 3,  "label": "沪深300 PE"},
    "SHIBOR": {"max_days": 3,  "label": "SHIBOR 隔夜"},
    "RMB":  {"max_days": 3,  "label": "人民币汇率"},
    "M2":   {"max_days": 45, "label": "M2 货币供应"},
    "PMI":  {"max_days": 35, "label": "PMI 制造业"},
    "CPI":  {"max_days": 35, "label": "CPI 消费价格"},
}

LOG_FILE = _MP_ROOT / "data" / "freshness.log"


def check_health():
    """调用 health API 获取数据新鲜度"""
    try:
        req = urllib.request.Request(HEALTH_ENDPOINT_URL)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("data", {}).get("data_freshness", {})
    except Exception as e:
        print(f"[ERROR] 无法连接 health API: {e}")
        return None


def check_macro_source(source_name, macro_data_dir):
    """检查某个宏观数据 .day 文件的最新日期"""
    day_dir = Path(macro_data_dir)
    if not day_dir.exists():
        return None

    # 找到对应的 .day 文件
    tag_map = {"M2": "M2", "PMI": "PMI", "CPI": "CPI",
               "SHIBOR": "SHIBOR", "RMB": "RMBUS"}
    tag = tag_map.get(source_name, source_name)

    import struct
    latest = None
    for f in day_dir.glob("*.day"):
        if tag.upper() in f.stem.upper() and len(f.stem) < 20:
            with open(f, "rb") as fh:
                data = fh.read()
            for i in range(0, len(data), 32):
                dt_int = struct.unpack("<I", data[i:i+4])[0]
                if 19900101 < dt_int < 21000000:
                    dt_str = str(dt_int)
                    dt = datetime.strptime(dt_str, "%Y%m%d")
                    if latest is None or dt > latest:
                        latest = dt
    return latest


def send_alert_if_needed(issues, alert_mode):
    """根据告警模式发送通知"""
    if not issues:
        return
    
    alert_msg = "⚠️ MarketPulse 数据过期告警:\n" + "\n".join(f"  {i}" for i in issues)
    
    # 写入告警旗标文件（unified_scheduler / CowAgent 可监控）
    ALERT_FLAG = _MP_ROOT / "data" / ".freshness_alert"
    with open(ALERT_FLAG, "w", encoding="utf-8") as f:
        f.write(alert_msg)
    
    # CowAgent 飞书 webhook 模式
    if alert_mode == "feishu":
        try:
            import requests
            webhook = os.environ.get("FEISHU_WEBHOOK", "")
            if webhook:
                requests.post(webhook, json={
                    "msg_type": "text",
                    "content": {"text": alert_msg}
                }, timeout=5)
        except Exception as e:
            print(f"  [WARN] 飞书告警发送失败: {e}")
    
    # 微信模板消息模式
    elif alert_mode == "wechat":
        # 写入 CowAgent 可识别的消息旗标
        WECHAT_FLAG = _MP_ROOT / "data" / ".wechat_alert"
        with open(WECHAT_FLAG, "w", encoding="utf-8") as f:
            f.write(alert_msg)


def run(alert=False, alert_mode="file"):
    """执行新鲜度检查"""
    today = datetime.now()
    issues = []

    # 1. 从 health API 获取 PE 新鲜度
    freshness = check_health()
    if freshness:
        pe_data = freshness.get("pe_data", {})
        if pe_data:
            pe_latest = pe_data.get("latest_date", "")
            if pe_latest:
                pe_date = datetime.strptime(pe_latest[:10], "%Y-%m-%d")
                pe_age = (today - pe_date).days
                if pe_age > THRESHOLDS["PE"]["max_days"]:
                    issues.append(f"🔴 {THRESHOLDS['PE']['label']}: {pe_latest[:10]} ({pe_age}天前，阈值{THRESHOLDS['PE']['max_days']}天)")

    # 2. 检查宏观数据源
    from config import MACRO_DATA_DIR
    for source_name in ["M2", "PMI", "CPI", "SHIBOR", "RMB"]:
        latest = check_macro_source(source_name, MACRO_DATA_DIR)
        cfg = THRESHOLDS.get(source_name)
        if latest and cfg:
            age = (today - latest).days
            if age > cfg["max_days"]:
                issues.append(f"🔴 {cfg['label']}: {latest.strftime('%Y-%m-%d')} ({age}天前，阈值{cfg['max_days']}天)")

    # 3. 输出
    timestamp = today.strftime("%Y-%m-%d %H:%M:%S")
    if issues:
        msg = f"[{timestamp}] ⚠️ 数据过期告警 ({len(issues)}项):\n" + "\n".join(f"  {i}" for i in issues)
        print(msg)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        
        if alert:
            send_alert_if_needed(issues, alert_mode)
        
        return issues
    else:
        msg = f"[{timestamp}] ✅ 数据新鲜度正常"
        print(msg)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        # 清除之前的告警旗标
        ALERT_FLAG = _MP_ROOT / "data" / ".freshness_alert"
        if ALERT_FLAG.exists():
            ALERT_FLAG.unlink()
        return []


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="MarketPulse 数据新鲜度检查")
    p.add_argument("--alert", action="store_true", help="过期时触发飞书告警")
    args = p.parse_args()
    issues = run(alert=args.alert)
    if issues:
        sys.exit(1)  # 非0退出码，方便调度器感知
