"""
MarketPulse API — Python 基础调用示例

依赖: pip install requests pandas matplotlib
"""

import requests
import pandas as pd
from datetime import datetime

# ── 配置 ────────────────────────────────────────────
API_BASE = "http://localhost:8898"
API_KEY = "mp-xxxxxxxx"  # 替换为你的 Key

headers = {"X-API-Key": API_KEY}


def call(endpoint: str) -> dict:
    """通用 API 调用"""
    resp = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("="*60)


# ── 1. PE 分位 ───────────────────────────────────────
print_section("1. PE 分位 — 估值温度计")
data = call("/api/v1/signal/pe-percentile")
d = data["data"]
print(f"  当前PE: {d['value']}")
print(f"  历史分位: {d['percentile']}%")
print(f"  解读: {d['interpretation']}")
print(f"  数据日期: {d['as_of_date']}")


# ── 2. ERP 股债性价比 ────────────────────────────────
print_section("2. ERP — 股债性价比")
data = call("/api/v1/signal/erp")
d = data["data"]
print(f"  ERP: {d['value']}%")
print(f"  盈利收益率: {d['earnings_yield']}%")
print(f"  10年国债: {d['bond_yield_10y']}%")
print(f"  解读: {d['interpretation']}")


# ── 3. 宏观评分 ──────────────────────────────────────
print_section("3. 宏观综合评分 — 六维度合成")
data = call("/api/v1/signal/macro-score")
d = data["data"]
print(f"  综合评分: {d['value']}/100")
print(f"  解读: {d['interpretation']}")
print(f"  有效维度: {d['dimensions_valid']}/{d['dimensions_total']}")
print("  子指标:")
for key, sub in d["sub_scores"].items():
    if sub["value"] is not None:
        print(f"    {key}: {sub['value']}{sub.get('unit','')} → 得分 {sub['score']}")


# ── 4. 行业宽度 ──────────────────────────────────────
print_section("4. 行业宽度 — 32 行业趋势分布")
data = call("/api/v1/signal/sector-breadth")
d = data["data"]
print(f"  行业宽度: {d['above_ma60_count']}/{d['sector_count']} ({d['value']*100:.1f}%)")
print(f"  趋势: {d['breadth_trend']}")
print(f"  风险偏好: {d['risk_appetite']}")
print(f"  解读: {d['interpretation']}")
print("  Top 5 行业:")
for s in d["top_5_sectors"]:
    print(f"    {s['name']} 动量 {s['momentum_60d']}%")
print("  Bottom 5 行业:")
for s in d["bottom_5_sectors"]:
    print(f"    {s['name']} 动量 {s['momentum_60d']}%")


# ── 5. 简单仪表盘 ────────────────────────────────────
print_section("5. 快速仪表盘")
df = pd.DataFrame({
    "指标": ["PE分位", "ERP", "宏观评分", "行业宽度"],
    "数值": [
        f"{call('/api/v1/signal/pe-percentile')['data']['percentile']}%",
        f"{call('/api/v1/signal/erp')['data']['value']}%",
        f"{call('/api/v1/signal/macro-score')['data']['value']}/100",
        f"{call('/api/v1/signal/sector-breadth')['data']['value']*100:.1f}%",
    ],
    "解读": [
        call('/api/v1/signal/pe-percentile')['data']['interpretation'],
        call('/api/v1/signal/erp')['data']['interpretation'][:10],
        call('/api/v1/signal/macro-score')['data']['interpretation'],
        call('/api/v1/signal/sector-breadth')['data']['interpretation'],
    ],
})
print(df.to_string(index=False))

print(f"\n⚡ 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"⚠️  {data['meta']['disclaimer']}")
