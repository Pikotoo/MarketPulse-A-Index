"""
资金情绪分 — 综合北向+融资+ETF三类资金流，判断市场资金面多空

指标 (3维聚合):
  1. 北向资金情绪 — 来自 northbound.py (权重 0.35)
  2. 融资融券情绪 — 来自 margin.py (权重 0.35)
  3. ETF 资金流方向 — 增量申赎趋势 (权重 0.30)

输出: 0-100 分，聚合三类资金的情绪信号
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


def _score_etf_flow() -> dict:
    """ETF 净申赎趋势 — 近20日变化"""
    try:
        # ETF 融资余额数据
        df = read_macro_series("SETF")
        if df is None or len(df) < 21:
            return {"value": None, "sub_score": None}

        latest_ma5 = float(df["close"].iloc[-5:].mean())
        past_ma20 = float(df["close"].iloc[-20:].mean())

        if past_ma20 <= 0:
            return {"value": None, "sub_score": None}

        change = round((latest_ma5 / past_ma20 - 1) * 100, 2)

        # -10% ~ +20% → 0-1
        def _norm(v, lo, hi):
            if v is None: return 0.0
            if v <= lo: return 0.0
            if v >= hi: return 1.0
            return (v - lo) / (hi - lo)

        s = _norm(change, -10.0, 20.0)
        return {"value": change, "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.30, 4)}
    except Exception:
        return {"value": None, "sub_score": None}


def _score_northbound_sub() -> dict:
    """从北向情绪分取子分"""
    try:
        from api.signals.northbound import get_northbound_sentiment
        r = get_northbound_sentiment(days=0)
        v = r.get("value")
        if v is not None:
            return {"value": v, "unit": "/100", "sub_score": round(float(v) * 0.0035, 4)}
    except Exception:
        pass
    return {"value": None, "sub_score": None}


def _score_margin_sub() -> dict:
    """从融资情绪分取子分"""
    try:
        from api.signals.margin import get_margin_sentiment
        r = get_margin_sentiment(days=0)
        v = r.get("value")
        if v is not None:
            return {"value": v, "unit": "/100", "sub_score": round(float(v) * 0.0035, 4)}
    except Exception:
        pass
    return {"value": None, "sub_score": None}


def _interpret(score):
    if score < 25: return "[算法输出] 资金全面流出——市场情绪极度悲观"
    elif score < 40: return "[算法输出] 资金偏流出——观望为主"
    elif score < 55: return "[算法输出] 资金面中性——多空基本平衡"
    elif score < 70: return "[算法输出] 资金偏流入——做多意愿增强"
    elif score < 85: return "[算法输出] 资金积极流入——多方占优"
    return "[算法输出] 资金全面涌入——情绪可能过热"


def get_fund_sentiment(days: int = 0) -> dict:
    """资金情绪分 0-100"""
    if days > 0:
        return {"indicator": "fund_sentiment", "status": "not_implemented",
                "note": "历史序列暂未实现", "history": []}

    s1 = _score_northbound_sub()
    s2 = _score_margin_sub()
    s3 = _score_etf_flow()

    subs = {"northbound": s1, "margin": s2, "etf_flow": s3}
    valid = [s["sub_score"] for s in subs.values() if s["sub_score"] is not None]
    n = len(valid)
    if n == 0:
        return {"indicator": "fund_sentiment", "value": None, "status": "no_data", "sub_scores": subs}

    total = round(sum(valid) / n * 3 * 100, 1)
    return {
        "indicator": "fund_sentiment", "value": total, "range": "0-100",
        "interpretation": _interpret(total), "sub_scores": subs,
        "dimensions_valid": n, "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
