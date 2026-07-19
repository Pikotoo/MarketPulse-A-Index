"""
恐贪指数回测验证

验证复合情绪分对沪深300未来收益的预测能力。

用法:
  py -3.11 scripts/backtest_composite.py

输出:
  - IC 相关系数（1月/3月/6月）
  - 分桶收益分析（极度恐惧→极度贪婪）
  - 买入持有策略 vs 恐贪择时策略对比
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

_MP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_MP_ROOT))

import numpy as np
import pandas as pd

from api.day_reader import read_macro_series
from config import MACRO_DATA_DIR


def load_index(path: str) -> pd.DataFrame:
    """加载指数日线 .day 文件"""
    import struct
    records = []
    with open(path, "rb") as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32:
                break
            dt_int, o, h, l, c, amt, vol, _res = struct.unpack("<IfffffII", chunk)
            if 20000101 < dt_int < 21000000:
                dt = pd.Timestamp(str(dt_int))
                records.append({"date": dt, "close": c})
    df = pd.DataFrame(records).sort_values("date")
    df.set_index("date", inplace=True)
    return df


def compute_score_for_date(target_date: pd.Timestamp) -> dict:
    """计算指定日期的综合情绪分（复用 composite 模块逻辑）"""
    from api.signals.composite import (
        _score_pe, _score_erp_value, _compute_erp_from_pe,
        _score_macro, _score_breadth, _get_bond_yield_latest
    )
    from api.signals.pe import _load_pe_data

    pe_data = _load_pe_data()
    if pe_data is None:
        return None

    pe_data["date"] = pd.to_datetime(pe_data["date"])
    pe_data = pe_data.sort_values("date")

    # PE 分位
    lookback = target_date - pd.Timedelta(days=5*365)
    hist = pe_data[(pe_data["date"] >= lookback) & (pe_data["date"] <= target_date)]
    current = pe_data[pe_data["date"] <= target_date]
    if len(current) == 0:
        return None
    pe_val = float(current["pe"].iloc[-1])
    if len(hist) >= 100:
        pct = round((hist["pe"] < pe_val).sum() / len(hist) * 100, 1)
    else:
        pct = None

    pe_sub = _score_pe(pct) if pct is not None else None

    # ERP (用最新债券利率 + 历史 PE)
    bond_yield = _get_bond_yield_latest()
    erp = _compute_erp_from_pe(pe_val, bond_yield)
    erp_sub = _score_erp_value(erp) if erp is not None else None

    # 宏观评分（历史回算，慢但准）
    macro_sub = _score_macro(as_of=target_date)

    # 行业宽度（历史回算）
    breadth_sub = _score_breadth(as_of=target_date)

    valid = [v for v in [pe_sub, erp_sub, macro_sub, breadth_sub] if v is not None]

    if len(valid) < 3:
        return None

    total = round(sum(valid), 1)
    return {
        "date": target_date,
        "score": total,
        "pe_pct": pct,
        "pe_sub": pe_sub,
        "erp_sub": erp_sub,
        "macro_sub": macro_sub,
        "breadth_sub": breadth_sub,
        "n_valid": len(valid),
    }


def run_backtest(start_year: int = 2016, end_year: int = 2026):
    """运行回测"""
    print("=" * 60)
    print("  MarketPulse 恐贪指数回测")
    print("=" * 60)

    # 加载沪深300指数
    index_path = Path(r"H:\数据大全\指数行情\上证指数\sh000300.day")
    if not index_path.exists():
        print("❌ 找不到沪深300指数数据")
        return

    print(f"\n📊 加载沪深300指数: {index_path}")
    index = load_index(str(index_path))
    print(f"   {len(index)} 条日线, {index.index[0].date()} ~ {index.index[-1].date()}")

    # 每月采样
    months = pd.date_range(
        start=pd.Timestamp(f"{start_year}-01-01"),
        end=pd.Timestamp(f"{end_year}-06-30"),
        freq="MS"
    )

    results = []
    total = len(months)
    print(f"\n🔬 计算 {total} 个月度采样点（每月初）...")

    for i, month_start in enumerate(months):
        # 向后找该月第一个有数据的交易日
        cursor = month_start
        for _ in range(10):
            if cursor in index.index or cursor.strftime("%Y-%m-%d") in [str(d.date()) for d in index.index[:3]]:
                break
            cursor += pd.Timedelta(days=1)

        # 找最近的PE数据
        pe_date = cursor - pd.Timedelta(days=0)
        result = compute_score_for_date(pe_date)
        if result is None:
            continue

        # 计算前向收益
        fwd_1m = fwd_3m = fwd_6m = None
        for fwd_months, key in [(1, "fwd_1m"), (3, "fwd_3m"), (6, "fwd_6m")]:
            future = cursor + pd.Timedelta(days=fwd_months * 31)
            future_data = index[index.index >= future]
            if len(future_data) > 0:
                future_close = float(future_data["close"].iloc[0])
            else:
                future_data = index[index.index <= future]
                if len(future_data) > 0:
                    future_close = float(future_data["close"].iloc[-1])
                else:
                    continue

            if cursor in index.index:
                current_close = float(index.loc[cursor, "close"])
            else:
                nearby = index[index.index <= cursor]
                if len(nearby) == 0:
                    continue
                current_close = float(nearby["close"].iloc[-1])

            ret = (future_close / current_close - 1) * 100
            if fwd_months == 1:
                fwd_1m = ret
            elif fwd_months == 3:
                fwd_3m = ret
            elif fwd_months == 6:
                fwd_6m = ret

        result["fwd_1m"] = fwd_1m
        result["fwd_3m"] = fwd_3m
        result["fwd_6m"] = fwd_6m
        results.append(result)

        if (i + 1) % 20 == 0:
            print(f"   {i+1}/{total} ({result['date'].strftime('%Y-%m')} score={result['score']})")

    if len(results) == 0:
        print("❌ 无有效采样点")
        return

    df = pd.DataFrame(results)
    print(f"\n✅ 有效采样: {len(df)} 个月")
    print(f"   得分范围: {df['score'].min():.1f} ~ {df['score'].max():.1f}")

    # IC 计算
    print("\n" + "=" * 60)
    print("  📈 预测能力 (Rank IC)")
    print("=" * 60)

    for label, col in [("1月", "fwd_1m"), ("3月", "fwd_3m"), ("6月", "fwd_6m")]:
        valid = df[df[col].notna()]
        if len(valid) < 10:
            print(f"  {label}: 数据不足")
            continue
        # Spearman rank correlation
        ic = valid["score"].corr(valid[col], method="spearman")
        pearson = valid["score"].corr(valid[col])
        print(f"  {label}: Spearman IC={ic:+.3f}  Pearson={pearson:+.3f}  n={len(valid)}")

    # 分桶分析
    print("\n" + "=" * 60)
    print("  🪣 分桶收益（按恐贪指数分组）")
    print("=" * 60)

    buckets = [
        (0, 20, "极度恐惧"),
        (20, 35, "恐惧"),
        (35, 45, "偏恐惧"),
        (45, 55, "中性"),
        (55, 65, "偏贪婪"),
        (65, 80, "贪婪"),
        (80, 100, "极度贪婪"),
    ]

    print(f"\n{'区间':<12} {'次数':>5} {'1月均':>8} {'3月均':>8} {'6月均':>8} {'胜率':>6}")
    print("-" * 55)

    for lo, hi, label in buckets:
        subset = df[(df["score"] >= lo) & (df["score"] < hi)]
        n = len(subset)
        if n == 0:
            continue
        m1 = subset["fwd_1m"].mean() if subset["fwd_1m"].notna().sum() > 0 else 0
        m3 = subset["fwd_3m"].mean() if subset["fwd_3m"].notna().sum() > 0 else 0
        m6 = subset["fwd_6m"].mean() if subset["fwd_6m"].notna().sum() > 0 else 0
        wr = (subset["fwd_1m"] > 0).mean() * 100 if subset["fwd_1m"].notna().sum() > 0 else 0
        print(f"{label:<12} {n:>5} {m1:>+7.1f}% {m3:>+7.1f}% {m6:>+7.1f}% {wr:>5.0f}%")

    # 择时策略对比
    print("\n" + "=" * 60)
    print("  🎯 策略对比")
    print("=" * 60)

    # 买入持有
    bh_start = df["date"].iloc[0]
    bh_end = df["date"].iloc[-1]
    bh_start_idx = index[index.index >= bh_start]
    bh_end_idx = index[index.index <= (bh_end + pd.Timedelta(days=31))]
    if len(bh_start_idx) > 0 and len(bh_end_idx) > 0:
        bh_ret = (float(bh_end_idx["close"].iloc[-1]) / float(bh_start_idx["close"].iloc[0]) - 1) * 100
        print(f"  买入持有: {bh_ret:+.1f}%  ({bh_start.strftime('%Y-%m')} → {bh_end.strftime('%Y-%m')})")

    # 恐贪择时: 分位 < 30 买入, 持有到 > 70 卖出
    position = 0
    trades = 0
    total_ret = 0
    entry_price = None

    for _, row in df.sort_values("date").iterrows():
        score = row["score"]
        if score < 30 and position == 0:
            # 买入
            d = row["date"]
            nearby = index[index.index <= d]
            if len(nearby) > 0:
                entry_price = float(nearby["close"].iloc[-1])
                position = 1
                trades += 1
        elif score > 70 and position == 1:
            # 卖出
            d = row["date"]
            nearby = index[index.index <= d]
            if len(nearby) > 0:
                exit_price = float(nearby["close"].iloc[-1])
                total_ret += (exit_price / entry_price - 1) * 100
                position = 0

    if trades > 0:
        print(f"  恐贪择时: {total_ret:+.1f}%  ({trades}笔交易, 阈值<30买 >70卖)")
        if trades > 2:
            print(f"  年均收益: {total_ret / ((end_year - start_year)):.1f}%/年")

    # 导出CSV
    output = _MP_ROOT / "data" / "backtest_results.csv"
    df_out = df[["date", "score", "pe_pct", "fwd_1m", "fwd_3m", "fwd_6m"]].copy()
    df_out["date"] = df_out["date"].apply(lambda x: x.strftime("%Y-%m-%d"))
    df_out.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"\n📁 详细数据已导出: {output}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=2016, help="起始年份")
    p.add_argument("--end", type=int, default=2026, help="结束年份")
    args = p.parse_args()
    run_backtest(args.start, args.end)
