"""
MarketPulse — 一键演示脚本
双击运行即可，无需任何操作。

会自动启动 API 服务、调用 4 个指标、显示结果。
看完按回车关闭。
"""

import sys
import os
import time
import threading
import subprocess

# ── 1. 启动 API 服务（后台运行）────────────────────
print("🚀 正在启动 MarketPulse API 服务...")

server_process = subprocess.Popen(
    [sys.executable, "-u", "api/app.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    cwd=os.path.dirname(os.path.abspath(__file__))
)

# 等待服务就绪
import requests
URL = "http://localhost:8898"
# 使用默认仪表盘 Key，或设置 DASHBOARD_KEY 环境变量
API_KEY = os.getenv("DASHBOARD_KEY", "mp-806fac606a6e1ce607ce158175087ca9")
headers = {"X-API-Key": API_KEY}

ready = False
for i in range(15):
    try:
        r = requests.get(f"{URL}/api/v1/health", timeout=2)
        if r.status_code == 200:
            ready = True
            break
    except Exception:
        pass
    time.sleep(1)
    print(f"  等待服务启动... ({i+1}/15)")

if not ready:
    print("❌ API 服务启动失败，请确认 api/app.py 存在")
    input("\n按回车退出...")
    sys.exit(1)

print("   ✅ 服务已就绪\n")

# ── 2. 调用 4 个指标 ──────────────────────────────
def call(endpoint):
    resp = requests.get(URL + endpoint, headers=headers, timeout=15)
    return resp.json()

print("=" * 50)
print("  📊 MarketPulse 市场脉搏")
print("  2026年7月16日 A股市场快照")
print("=" * 50)

print("\n📌 1. PE 分位 — 现在估值贵不贵？")
try:
    d = call("/api/v1/signal/pe-percentile")["data"]
    print(f"   沪深300 PE = {d['value']}")
    print(f"   历史分位 = {d['percentile']}%（100% = 最贵）")
    print(f"   判断：{d['interpretation']}")
except Exception as e:
    print(f"   ❌ 获取失败: {e}")

print("\n📌 2. 股债性价比 — 买股票还是买债券？")
try:
    d = call("/api/v1/signal/erp")["data"]
    print(f"   买股票的预期年收益 = {d['earnings_yield']}%")
    print(f"   买国债的确定年收益 = {d['bond_yield_10y']}%")
    print(f"   股票多赚的（ERP）= {d['value']}%")
    print(f"   判断：{d['interpretation']}")
except Exception as e:
    print(f"   ❌ 获取失败: {e}")

print("\n📌 3. 宏观评分 — 经济环境好不好？")
try:
    d = call("/api/v1/signal/macro-score")["data"]
    print(f"   综合分 = {d['value']}/100（50 = 中性）")
    print(f"   判断：{d['interpretation']}")
except Exception as e:
    print(f"   ❌ 获取失败: {e}")

print("\n📌 4. 行业宽度 — 有多少行业在涨？")
try:
    d = call("/api/v1/signal/sector-breadth")["data"]
    print(f"   在涨的行业：{d['above_ma60_count']}/{d['sector_count']}（{d['value'] * 100:.1f}%）")
    print(f"   判断：{d['interpretation']}")
    print(f"   最近60天涨最多：")
    for s in d["top_5_sectors"]:
        print(f"     🟢 {s['name']:　<6s}  {s['momentum_60d']:+.2f}%")
    print(f"   最近60天跌最多：")
    for s in d["bottom_5_sectors"]:
        print(f"     🔴 {s['name']:　<6s}  {s['momentum_60d']:+.2f}%")
except Exception as e:
    print(f"   ❌ 获取失败: {e}")

print("\n" + "=" * 50)
print("  ⚠️  以上数据仅供研究参考，不构成投资建议")
print("=" * 50)

# ── 3. 清理 ─────────────────────────────────────
server_process.terminate()
input("\n按回车键退出...")
