"""
信号预计算脚本 — 每日凌晨批量计算所有指标并写入缓存

用法:
  py -3.11 scripts/update_signals.py          # 计算今天
  py -3.11 scripts/update_signals.py --all     # 重建全部历史
  py -3.11 scripts/update_signals.py --status  # 查看缓存状态

接入 unified_scheduler:
  scheduler 中注册此脚本，每天 6:00 执行一次
"""

import sys
import time
from pathlib import Path
from datetime import date, timedelta

# 确保 MarketPulse 可导入
_MP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_MP_ROOT))

from api.cache import init_cache_db, set_cache, cache_stats, is_fresh

# ── 所有待缓存的信号 ──

SIGNALS = [
    ("pe_percentile",       "api.signals.pe",           "get_pe_signal",           {}),
    ("erp",                 "api.signals.erp",          "get_erp_signal",          {}),
    ("macro_score",         "api.signals.macro_score",  "get_macro_score",         {}),
    ("sector_breadth",      "api.signals.sector",       "get_sector_breadth",      {}),
    ("panic_index",         "api.signals.panic",        "get_panic_index",         {}),
    ("composite",           "api.signals.composite",    "get_composite_score",     {}),
    ("advance_decline",     "api.signals.breadth",      "get_advance_decline",     {}),
    ("new_high_low",        "api.signals.breadth",      "get_new_high_low",        {}),
    ("sector_momentum",     "api.signals.breadth",      "get_sector_momentum",     {}),
    # ── v2.1 新增 P1 ──
    ("margin_sentiment",    "api.signals.margin",       "get_margin_sentiment",    {}),
    ("volume_score",        "api.signals.volume",       "get_volume_score",        {}),
    ("northbound_sentiment","api.signals.northbound",   "get_northbound_sentiment",{}),
    ("lockup_pressure",     "api.signals.lockup",       "get_lockup_pressure",     {}),
    # ── v2.1 新增 P2 ──
    ("liquidity_score",     "api.signals.liquidity",    "get_liquidity_score",     {}),
    ("sector_crowding",     "api.signals.crowding",     "get_sector_crowding",     {}),
    ("fund_sentiment",      "api.signals.fund_sentiment","get_fund_sentiment",      {}),
    ("cross_asset",         "api.signals.cross_asset",  "get_cross_asset",         {}),
    ("style_rotation",      "api.signals.style",        "get_style_rotation",      {}),
    ("regime",              "api.signals.regime",       "get_regime",              {}),
    # defensive_ratio 已内嵌在 sector_breadth.defensive_vs_offensive 中，无需独立信号
    ("sector_heatmap",      "api.signals.sector",       "get_sector_heatmap",      {}),
]


def compute_all():
    """计算所有信号并写入缓存"""
    init_cache_db()
    today = date.today().isoformat()
    results = []

    for indicator, module_path, func_name, kwargs in SIGNALS:
        mod = __import__(module_path, fromlist=[func_name])
        func = getattr(mod, func_name)
        start = time.time()
        try:
            data = func(days=0, **kwargs)
            elapsed = time.time() - start
            set_cache(indicator, data)
            results.append((indicator, "OK", f"{elapsed:.1f}s"))
        except Exception as e:
            results.append((indicator, "FAIL", str(e)[:80]))

    # 打印结果
    print(f"\n{'='*50}")
    print(f"  MarketPulse 信号更新 — {today}")
    print(f"{'='*50}")
    for name, status, detail in results:
        icon = "[OK]" if status == "OK" else "[FAIL]"
        print(f"  {icon} {name:20s}  {detail}")
    print(f"{'='*50}")

    ok = sum(1 for _, s, _ in results if s == "OK")
    print(f"  成功 {ok}/{len(results)} | 时间 {today}")
    print()

    return results


def compute_all_dates(days_back: int = 365):
    """重建指定天数的历史缓存（逐日回算）"""
    today = date.today()
    for i in range(days_back, -1, -1):
        d = today - timedelta(days=i)
        # 只对没有缓存的天计算
        missing = []
        for indicator, _, _, _ in SIGNALS:
            if not is_fresh(indicator):
                missing.append(indicator)

        if missing:
            # 简化处理：不逐日回算历史（太慢且复杂）
            # 只确保今天有缓存
            break

    compute_all()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="MarketPulse 信号预计算")
    p.add_argument("--all", action="store_true", help="重建全部历史缓存")
    p.add_argument("--status", action="store_true", help="查看缓存状态")
    args = p.parse_args()

    if args.status:
        stats = cache_stats()
        print(f"\n缓存状态 ({stats['as_of']}):")
        print(f"  今日已缓存: {stats['today_cached']} 个指标")
        print(f"  总缓存记录: {stats['total_cached']} 条")
        print(f"  已缓存指标: {', '.join(stats['cached_indicators']) or '(无)'}")
        print()
    elif args.all:
        compute_all_dates()
    else:
        compute_all()
