"""
流动性评分 — 多维度资金面松紧综合评分

指标 (4维):
  1. SHIBOR 短端利差 — 1W vs ON 的陡峭程度（资金面预期）
  2. M1-M2 剪刀差 — 货币活化/沉淀
  3. MLF-LPR 利差 — 政策利率传导效率
  4. SHIBOR 绝对水平 — 隔夜利率位置

输出: 0-100 分，越高=流动性越宽松
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import numpy as np
import pandas as pd
from datetime import date
from typing import Optional

from api.day_reader import read_macro_series


def _norm(v, lo, hi):
    if v is None: return 0.0
    if v <= lo: return 0.0
    if v >= hi: return 1.0
    return (v - lo) / (hi - lo)


def _rnorm(v, lo, hi):
    return 1.0 - _norm(v, lo, hi)


def _val(code, as_of=None, months=1):
    try:
        df = read_macro_series(code)
        if as_of is not None: df = df[df.index <= as_of]
        if len(df) == 0: return None
        return float(df["close"].iloc[-months:].mean())
    except Exception:
        return None


def _yoy(code, as_of=None, lag=12):
    try:
        df = read_macro_series(code)
        if as_of is not None: df = df[df.index <= as_of]
        if len(df) < lag + 1: return None
        latest = float(df["close"].iloc[-1])
        past = float(df["close"].iloc[-(lag + 1)])
        return (latest / past - 1) * 100 if past > 0 else None
    except Exception:
        return None


def _score_shibor_level(as_of=None):
    """SHIBOR 隔夜绝对水平 → 越低越宽松"""
    v = _val("SHIBOR_ON", as_of, months=1)
    if v is None: return {"value": None, "sub_score": None}
    s = _rnorm(v, 1.0, 3.5)
    return {"value": round(v, 3), "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.30, 4)}


def _score_shibor_slope(as_of=None):
    """SHIBOR 1W vs ON 利差 → 正利差=正常，倒挂=紧张"""
    on = _val("SHIBOR_ON", as_of)
    w1 = _val("SHIBOR_1W", as_of)
    if on is None or w1 is None: return {"value": None, "sub_score": None}
    spread = w1 - on
    s = _norm(spread, -0.1, 0.5)
    return {"value": round(spread, 3), "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.25, 4)}


def _score_m1m2_spread(as_of=None):
    """M1-M2 剪刀差 → 活化程度"""
    m1 = _yoy("M1", as_of)
    m2 = _yoy("M2", as_of)
    if m1 is None or m2 is None: return {"value": None, "sub_score": None}
    spread = m1 - m2
    s = _norm(spread, -12.0, 5.0)
    return {"value": round(spread, 2), "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.25, 4)}


def _score_mlf_lpr(as_of=None):
    """MLF - LPR 利差 → 银行净息差空间"""
    mlf = _val("MLF1Y", as_of)
    lpr = _val("LPR1Y", as_of)
    if mlf is None or lpr is None: return {"value": None, "sub_score": None}
    spread = lpr - mlf
    s = _norm(spread, 0.5, 2.0)
    return {"value": round(spread, 3), "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.20, 4)}


def _interpret(score):
    if score < 25: return "[算法输出] 流动性极度紧张"
    elif score < 40: return "[算法输出] 流动性偏紧"
    elif score < 55: return "[算法输出] 流动性中性"
    elif score < 70: return "[算法输出] 流动性偏宽松"
    elif score < 85: return "[算法输出] 流动性宽松"
    return "[算法输出] 流动性极度宽松"


def get_liquidity_score(days: int = 0) -> dict:
    """流动性评分 0-100"""
    if days > 0:
        return {"indicator": "liquidity_score", "status": "not_implemented",
                "note": "历史序列暂未实现", "history": []}

    s1 = _score_shibor_level()
    s2 = _score_shibor_slope()
    s3 = _score_m1m2_spread()
    s4 = _score_mlf_lpr()

    subs = {"shibor_level": s1, "shibor_slope": s2, "m1m2_spread": s3, "mlf_lpr_spread": s4}
    valid = [s["sub_score"] for s in subs.values() if s["sub_score"] is not None]
    n = len(valid)
    if n == 0:
        return {"indicator": "liquidity_score", "value": None, "status": "no_data", "sub_scores": subs}

    total = round(sum(valid) / n * 4 * 100, 1)
    return {
        "indicator": "liquidity_score", "value": total, "range": "0-100",
        "interpretation": _interpret(total), "sub_scores": subs,
        "dimensions_valid": n, "dimensions_total": 4,
        "as_of_date": date.today().isoformat(),
    }
