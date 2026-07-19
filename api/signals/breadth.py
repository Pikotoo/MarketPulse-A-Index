"""
全市场宽度指标 — 涨跌家数比 & 新高新低 & 行业动量排名

基于申万32行业指数日线数据，计算市场宽度信号。
不涉及个股数据，全部从现有行业数据派生。

端点:
  GET /api/v1/signal/advance-decline  — 行业涨跌比
  GET /api/v1/signal/new-high-low      — 新高新低比
  GET /api/v1/signal/sector-momentum   — 行业动量完整排名
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import numpy as np
import pandas as pd
from datetime import date, timedelta

from api.signals.sector import SECTOR_NAMES, _load_sector, _momentum, _above_ma, get_sector_codes


def get_advance_decline(days: int = 0) -> dict:
    """
    行业涨跌比 — 今日上涨 vs 下跌的行业数量

    Returns:
        advancing: 上涨行业数
        declining: 下跌行业数
        ratio: 上涨/下跌比 (advancing/declining)
        unchanged: 平盘行业数
    """
    target = pd.Timestamp.now()
    codes = get_sector_codes()

    advancing = 0
    declining = 0
    unchanged = 0

    for code in codes:
        df = _load_sector(code)
        if df is None or len(df) < 2:
            continue
        today_close = float(df['close'].iloc[-1])
        yesterday_close = float(df['close'].iloc[-2])
        if today_close > yesterday_close:
            advancing += 1
        elif today_close < yesterday_close:
            declining += 1
        else:
            unchanged += 1

    total = advancing + declining + unchanged
    if total == 0:
        return {"indicator": "advance_decline", "status": "no_data"}

    ratio = round(advancing / declining, 2) if declining > 0 else (99.0 if advancing > 0 else 1.0)

    if ratio > 3:
        mood = "极度乐观"
    elif ratio > 2:
        mood = "乐观"
    elif ratio > 1.2:
        mood = "偏乐观"
    elif ratio > 0.8:
        mood = "均衡"
    elif ratio > 0.5:
        mood = "偏悲观"
    elif ratio > 0.3:
        mood = "悲观"
    else:
        mood = "极度悲观"

    # 历史序列
    history = []
    if days > 0:
        days = min(days, 365)
        cursor = pd.Timestamp.now() - pd.Timedelta(days=days)
        while cursor <= pd.Timestamp.now():
            if cursor.dayofweek < 5:
                adv = 0; dec = 0
                for code in codes:
                    df = _load_sector(code)
                    if df is not None and len(df) >= 2:
                        # 找cursor日期附近的数据
                        nearby = df[df.index <= cursor]
                        if len(nearby) >= 2:
                            t = float(nearby['close'].iloc[-1])
                            y = float(nearby['close'].iloc[-2])
                            if t > y: adv += 1
                            elif t < y: dec += 1
                if adv + dec > 0:
                    history.append({
                        "date": cursor.strftime("%Y-%m-%d"),
                        "advancing": adv, "declining": dec,
                        "ratio": round(adv/dec, 2) if dec > 0 else 99.0,
                    })
            cursor += pd.Timedelta(days=3)
        return {"indicator": "advance_decline", "days": days, "samples": len(history),
                "history": history, "as_of_date": date.today().isoformat()}

    return {
        "indicator": "advance_decline",
        "advancing": advancing, "declining": declining, "unchanged": unchanged,
        "ratio": ratio, "total": total, "sentiment": mood,
        "as_of_date": date.today().isoformat(),
    }


# ── 新高新低 ─────────────────────────────────────────────

def get_new_high_low(days: int = 0, lookback: int = 60) -> dict:
    """
    行业新高新低比 — 创N日新高 vs N日新低的行业数量

    当日收盘价 ≥ 过去60日(默认)最高价 → 新高
    当日收盘价 ≤ 过去60日(默认)最低价 → 新低

    Returns:
        new_high: 创N日新高的行业数
        new_low: 创N日新低的行业数
        hl_ratio: 新高/新低比
        total: 有效行业总数
    """
    target = pd.Timestamp.now()
    codes = get_sector_codes()

    new_high = 0
    new_low = 0

    for code in codes:
        df = _load_sector(code)
        if df is None or len(df) < lookback + 1:
            continue
        window = df.iloc[-(lookback + 1):]
        today_close = float(window['close'].iloc[-1])
        hist_high = float(window['high'].iloc[:-1].max())
        hist_low = float(window['low'].iloc[:-1].min())

        if today_close >= hist_high * 0.995:  # 0.5% 容差
            new_high += 1
        if today_close <= hist_low * 1.005:
            new_low += 1

    total = len(codes)
    hl_ratio = round(new_high / new_low, 2) if new_low > 0 else 99.0

    if new_high > new_low * 2:
        trend = "强势突破"
    elif new_high > new_low:
        trend = "偏多"
    elif new_high == new_low:
        trend = "均衡"
    elif new_low > new_high * 2:
        trend = "弱势破位"
    else:
        trend = "偏空"

    # 历史序列
    history = []
    if days > 0:
        days = min(days, 365)
        cursor = pd.Timestamp.now() - pd.Timedelta(days=days)
        while cursor <= pd.Timestamp.now():
            if cursor.dayofweek < 5:
                nh = 0; nl = 0
                for code in codes:
                    df = _load_sector(code)
                    if df is not None and len(df) >= lookback + 1:
                        nearby = df[df.index <= cursor]
                        if len(nearby) >= lookback + 1:
                            w = nearby.iloc[-(lookback + 1):]
                            c_close = float(w['close'].iloc[-1])
                            h_high = float(w['high'].iloc[:-1].max())
                            h_low = float(w['low'].iloc[:-1].min())
                            if c_close >= h_high * 0.995: nh += 1
                            if c_close <= h_low * 1.005: nl += 1
                history.append({
                    "date": cursor.strftime("%Y-%m-%d"),
                    "new_high": nh, "new_low": nl,
                })
            cursor += pd.Timedelta(days=3)
        return {"indicator": "new_high_low", "days": days, "samples": len(history),
                "history": history, "as_of_date": date.today().isoformat()}

    return {
        "indicator": "new_high_low",
        "new_high": new_high, "new_low": new_low,
        "hl_ratio": hl_ratio, "total": total,
        "lookback_days": lookback, "trend": trend,
        "as_of_date": date.today().isoformat(),
    }


# ── 行业动量排名 ──────────────────────────────────────────

def get_sector_momentum(days: int = 0, period: int = 60) -> dict:
    """
    行业动量排名 — 32行业按N日涨跌幅完整排序

    Returns:
        rankings: [{code, name, momentum_60d, above_ma60}, ...] 全部32行业排序
    """
    target = pd.Timestamp.now()
    codes = get_sector_codes()

    rankings = []
    for code in codes:
        df = _load_sector(code)
        if df is None or len(df) < period + 1:
            continue
        mom = round(_momentum(df, period, target) * 100, 2)
        name = SECTOR_NAMES.get(code, code)

        # 判断是否在 MA60 上方
        from api.signals.sector import _above_ma
        above = _above_ma(df, 60, target)

        rankings.append({
            "code": code,
            "name": name,
            "momentum": mom,
            "above_ma60": above,
        })

    rankings.sort(key=lambda x: x["momentum"], reverse=True)

    # 历史序列
    history = []
    if days > 0:
        days = min(days, 365)
        cursor = pd.Timestamp.now() - pd.Timedelta(days=days)
        while cursor <= pd.Timestamp.now():
            if cursor.dayofweek < 5:
                top3 = []
                for code in codes:
                    df = _load_sector(code)
                    if df is not None and len(df) >= period + 1:
                        mom = round(_momentum(df, period, cursor) * 100, 2)
                        top3.append({"code": code, "name": SECTOR_NAMES.get(code, code), "mom": mom})
                top3.sort(key=lambda x: x["mom"], reverse=True)
                history.append({
                    "date": cursor.strftime("%Y-%m-%d"),
                    "top3": top3[:3],
                    "bottom3": top3[-3:],
                })
            cursor += pd.Timedelta(days=4)
        return {"indicator": "sector_momentum", "period": period, "days": days,
                "samples": len(history), "history": history,
                "as_of_date": date.today().isoformat()}

    return {
        "indicator": "sector_momentum",
        "period": period,
        "rankings": rankings,
        "top_3": rankings[:3],
        "bottom_3": rankings[-3:],
        "as_of_date": date.today().isoformat(),
    }
