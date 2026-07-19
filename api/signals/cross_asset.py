"""
跨资产比较 — 股债商汇多资产对比信号

指标:
  1. 股债相对强度 — 沪深300 vs 10Y国债收益率变动的相对表现
  2. 商品/股票比 — 黄金 vs 沪深300（风险偏好指标）
  3. 人民币汇率趋势 — 汇率变动方向

输出: cross_asset_score 0-100
  >55: 风险资产占优（Risk On）
  <45: 避险资产占优（Risk Off）
  45-55: 均衡
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

from api.day_reader import read_macro_series, get_macro_value


def _norm(v, lo, hi):
    if v is None: return 0.0
    if v <= lo: return 0.0
    if v >= hi: return 1.0
    return (v - lo) / (hi - lo)


def _rnorm(v, lo, hi):
    return 1.0 - _norm(v, lo, hi)


def _yoy(code, as_of=None, lag=12):
    try:
        df = read_macro_series(code)
        if as_of is not None: df = df[df.index <= as_of]
        if len(df) < lag + 1: return None
        latest = float(df["close"].iloc[-1])
        past = float(df["close"].iloc[-(lag + 1)])
        return round((latest / past - 1) * 100, 2) if past > 0 else None
    except Exception:
        return None


def _score_stock_bond() -> dict:
    """股债相对强度 — 10Y国债收益率变化方向 vs 股市表现"""
    try:
        # 10Y 国债收益率 3个月变化（收益率上升=债跌）
        bond_yoy = _yoy("CNG10Y") or _yoy("CNDT10Y")
        # 用 PE 作为股市 proxy（PE上升=估值扩张=股市好）
        from api.signals.pe import _load_pe_data
        pe = _load_pe_data()
        if pe is None or len(pe) < 63:
            return {"value": None, "sub_score": None}

        pe_now = float(pe["pe"].iloc[-1])
        pe_3m_ago = float(pe["pe"].iloc[-63]) if len(pe) >= 63 else pe_now
        pe_change = round((pe_now / pe_3m_ago - 1) * 100, 2) if pe_3m_ago > 0 else 0

        # 股强（PE涨）+ 债弱（收益率升）= Risk On → 高分
        # 股弱（PE跌）+ 债强（收益率降）= Risk Off → 低分
        if bond_yoy is not None and pe_change is not None:
            combined = pe_change - (bond_yoy or 0) * 5  # PE变化 vs 利率变化（放大利率权重）
        else:
            return {"value": None, "sub_score": None}

        s = _norm(combined, -20.0, 20.0)
        return {"value": round(combined, 2), "score": round(s, 3),
                "sub_score": round(s * 0.40, 4),
                "pe_change_3m": pe_change, "bond_yield_change_3m": bond_yoy}
    except Exception:
        return {"value": None, "sub_score": None}


def _score_gold_stock() -> dict:
    """黄金/股票比 — 避险 vs 风险偏好"""
    try:
        gold_change = _yoy("GOLD", lag=3)  # 3个月黄金变化
        # 黄金涨 + 股市弱 = Risk Off（避险）
        # 黄金跌 + 股市强 = Risk On
        from api.signals.pe import _load_pe_data
        pe = _load_pe_data()
        if pe is None:
            return {"value": None, "sub_score": None}

        pe_now = float(pe["pe"].iloc[-1])
        pe_3m = float(pe["pe"].iloc[-63]) if len(pe) >= 63 else pe_now
        stock_change = round((pe_now / pe_3m - 1) * 100, 2) if pe_3m > 0 else 0

        if gold_change is not None:
            # 黄金跌+股票涨=最优，黄金涨+股票跌=最差
            combined = stock_change - (gold_change or 0)
        else:
            return {"value": None, "sub_score": None}

        s = _norm(combined, -15.0, 15.0)
        return {"value": round(combined, 2), "score": round(s, 3),
                "sub_score": round(s * 0.35, 4),
                "gold_change_3m": gold_change, "stock_change_3m": stock_change}
    except Exception:
        return {"value": None, "sub_score": None}


def _score_rmb_trend() -> dict:
    """人民币汇率趋势"""
    try:
        rmb = _yoy("RMBUS", lag=3) or _yoy("CNYUSD", lag=3)
        if rmb is None:
            return {"value": None, "sub_score": None}
        # 人民币升值（rmb负）=利好A股，贬值=利空
        s = _rnorm(rmb, -5.0, 5.0)  # 升值越高分
        return {"value": rmb, "unit": "%", "score": round(s, 3),
                "sub_score": round(s * 0.25, 4)}
    except Exception:
        return {"value": None, "sub_score": None}


def _interpret(score):
    if score < 30: return "[算法输出] Risk Off——避险资产全面占优"
    elif score < 45: return "[算法输出] 偏 Risk Off——资金偏向避险"
    elif score < 55: return "[算法输出] 均衡——多资产无明显偏向"
    elif score < 70: return "[算法输出] 偏 Risk On——风险资产略占优"
    else: return "[算法输出] Risk On——风险资产全面占优"


def get_cross_asset(days: int = 0) -> dict:
    """跨资产比较分 0-100"""
    if days > 0:
        return {"indicator": "cross_asset", "status": "not_implemented",
                "note": "历史序列暂未实现", "history": []}

    s1 = _score_stock_bond()
    s2 = _score_gold_stock()
    s3 = _score_rmb_trend()

    subs = {"stock_vs_bond": s1, "gold_vs_stock": s2, "rmb_trend": s3}
    valid = [s["sub_score"] for s in subs.values() if s["sub_score"] is not None]
    n = len(valid)
    if n == 0:
        return {"indicator": "cross_asset", "value": None, "status": "no_data", "sub_scores": subs}

    total = round(sum(valid) / n * 3 * 100, 1)
    return {
        "indicator": "cross_asset", "value": total, "range": "0-100",
        "interpretation": _interpret(total), "sub_scores": subs,
        "dimensions_valid": n, "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
