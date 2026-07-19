"""
宏观综合评分 — 多维宏观指标归一化合成 0-100 分

指标池 (9维度 → 归一化 → 等权合成):
  1. M2同比增速 — 流动性松紧
  2. PMI — 制造业景气度
  3. CPI — 通胀压力
  4. SHIBOR隔夜 — 短期资金面
  5. 国债期限利差 — 经济预期 (10Y - 2Y)
  6. 人民币汇率 — 资本流动方向
  7. PPI — 工业品出厂价（需求端温度）[v2.1新增]
  8. M1-M2 剪刀差 — 货币活化程度 [v2.1新增]
  9. FDI — 外商直接投资信心 [v2.1新增]

支持历史回算：传入 as_of 参数可计算指定日期的宏观评分。

数据来源: 国家统计局、中国人民银行、中债登公开数据
加工深度: 9个原始指标 → 各自归一化 → 等权合成 → 0-100单一分数
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

_EMPTY = {"value": None, "score": None, "sub_score": None, "note": "数据不可用"}


# ── 归一化 ────────────────────────────────────────────────

def _norm(v, lo, hi):
    if v is None: return 0
    if v <= lo: return 0.0
    if v >= hi: return 1.0
    return (v - lo) / (hi - lo)


def _rnorm(v, lo, hi):
    return 1.0 - _norm(v, lo, hi)


# ── 取值辅助 ──────────────────────────────────────────────

def _val(code, as_of=None, months=3):
    """取近N月均值"""
    try:
        df = read_macro_series(code)
        if as_of is not None:
            df = df[df.index <= as_of]
        if len(df) == 0: return None
        return float(df["close"].iloc[-months:].mean())
    except Exception:
        return None


def _yoy(code, as_of=None, lag=12):
    """同比变化率"""
    try:
        df = read_macro_series(code)
        if as_of is not None:
            df = df[df.index <= as_of]
        if len(df) < lag + 1: return None
        latest = float(df["close"].iloc[-1])
        year_ago = float(df["close"].iloc[-(lag + 1)])
        return (latest / year_ago - 1) * 100 if year_ago > 0 else None
    except Exception:
        return None


# ── 各子指标评分（支持 as_of）─────────────────────────────

def _score_m2(as_of=None):
    yoy = _yoy("M2", as_of)
    if yoy is None: return dict(_EMPTY)
    s = _norm(yoy, 6.0, 15.0)
    return {"value": round(yoy, 2), "unit": "%", "score": round(s, 3), "sub_score": round(s / 9, 4)}


def _score_pmi(as_of=None):
    v = _val("PMI", as_of)
    if v is None: return dict(_EMPTY)
    s = _norm(v, 48.0, 55.0)
    return {"value": round(v, 1), "unit": "", "score": round(s, 3), "sub_score": round(s / 9, 4)}


def _score_cpi(as_of=None):
    yoy = _yoy("CPI", as_of)
    if yoy is None: return dict(_EMPTY)
    if yoy < 0: s = 0.2
    elif yoy <= 1.0: s = _norm(yoy, 0.0, 3.0) * 0.8
    elif yoy <= 3.0: s = 0.8 + _norm(yoy, 1.0, 3.0) * 0.2
    else: s = max(0, 1.0 - _norm(yoy, 3.0, 8.0))
    return {"value": round(yoy, 2), "unit": "%", "score": round(s, 3), "sub_score": round(s / 9, 4)}


def _score_shibor(as_of=None):
    v = _val("SHIBOR_ON", as_of, months=1)
    if v is None: return dict(_EMPTY)
    s = _rnorm(v, 1.0, 4.0)
    return {"value": round(v, 3), "unit": "%", "score": round(s, 3), "sub_score": round(s / 9, 4)}


def _score_spread(as_of=None):
    y10 = _val("CNG10Y", as_of) or _val("CNDT10Y", as_of)
    y2 = _val("CNG2Y", as_of) or _val("CNDT2Y", as_of) or _val("CNDT5Y", as_of)
    if y10 is None or y2 is None: return dict(_EMPTY)
    spread = y10 - y2
    s = _norm(spread, 0.3, 2.5)
    return {"value": round(spread, 3), "unit": "%", "score": round(s, 3), "sub_score": round(s / 9, 4)}


def _score_rmb(as_of=None):
    v = _val("RMBUS", as_of, months=1) or _val("CNYUSD", as_of, months=1)
    if v is None: return dict(_EMPTY)
    s = _rnorm(v, 6.3, 7.8)
    return {"value": round(v, 4), "unit": "CNY/USD", "score": round(s, 3), "sub_score": round(s / 9, 4)}


# ── v2.1 新增维度 ──────────────────────────────────────────

def _score_ppi(as_of=None):
    """PPI 工业品出厂价格 — 反映工业需求端温度 [v2.1新增]"""
    yoy = _yoy("PPI", as_of)
    if yoy is None:
        return dict(_EMPTY)
    # PPI 合理区间 -3% ~ +5%，太高=原材料暴涨挤压利润，太低=需求萎缩
    if yoy < -5:
        s = 0.1
    elif yoy < -2:
        s = _norm(yoy, -5.0, 0.0) * 0.7 + 0.1
    elif yoy <= 3:
        s = 0.5 + _norm(yoy, -2.0, 3.0) * 0.4  # 温和通胀最优
    elif yoy <= 6:
        s = 0.9 - _norm(yoy, 3.0, 6.0) * 0.4  # 偏高，开始挤压利润
    else:
        s = 0.1  # 过高，成本端压力大
    return {"value": round(yoy, 2), "unit": "%", "score": round(s, 3), "sub_score": round(s / 9, 4)}


def _score_m1m2(as_of=None):
    """M1-M2 剪刀差 — 货币活化程度，剪刀差扩大=资金流入实体经济 [v2.1新增]"""
    m1_yoy = _yoy("M1", as_of)
    m2_yoy = _yoy("M2", as_of)
    if m1_yoy is None or m2_yoy is None:
        return dict(_EMPTY)
    spread = round(m1_yoy - m2_yoy, 2)
    # 剪刀差范围 -15% ~ +5%
    # 剪刀差 > 0 = 资金活化（M1增速>M2），经济活跃
    # 剪刀差 < 0 = 资金沉淀（定期化），经济谨慎
    s = _norm(spread, -12.0, 5.0)
    return {
        "value": spread, "unit": "%",
        "m1_yoy": round(m1_yoy, 2), "m2_yoy_dup": round(m2_yoy, 2),
        "score": round(s, 3), "sub_score": round(s / 9, 4),
    }


def _score_fdi(as_of=None):
    """FDI 外商直接投资 — 外资对中国经济的信心投票 [v2.1新增]"""
    yoy = _yoy("FDI", as_of)
    if yoy is None:
        return dict(_EMPTY)
    # FDI 变化范围 -30% ~ +30%
    s = _norm(yoy, -25.0, 25.0)
    return {"value": round(yoy, 2), "unit": "%", "score": round(s, 3), "sub_score": round(s / 9, 4)}


# ── 综合评分 ──────────────────────────────────────────────

def _interpret(score):
    if score < 20: return "[算法输出] 宏观环境极度寒冷"
    if score < 35: return "[算法输出] 宏观环境偏冷"
    if score < 45: return "[算法输出] 宏观环境中性偏冷"
    if score < 55: return "[算法输出] 宏观环境中性"
    if score < 65: return "[算法输出] 宏观环境中性偏暖"
    if score < 80: return "[算法输出] 宏观环境偏暖"
    return "[算法输出] 宏观环境火热"


def _compute(as_of=None):
    """计算宏观综合评分，返回 (composite, scores, n_valid)"""
    scorers = [_score_m2, _score_pmi, _score_cpi, _score_shibor, _score_spread, _score_rmb,
               _score_ppi, _score_m1m2, _score_fdi]
    scores = {f.__name__[7:]: f(as_of) for f in scorers}  # _score_m2 → m2
    valid = [s["sub_score"] for s in scores.values() if s["sub_score"] is not None]
    n = len(valid)
    if n == 0: return None, scores, 0
    composite = sum(valid) / n * 9 * 100  # 补齐缺失维度（9维）
    return composite, scores, n


def _macro_latest():
    composite, scores, n = _compute()
    if composite is None:
        return {"indicator": "macro_score", "value": None, "status": "no_data",
                "message": "所有宏观指标数据不可用", "sub_scores": scores}
    return {
        "indicator": "macro_score",
        "value": round(composite, 1), "range": "0-100",
        "interpretation": _interpret(composite),
        "percentile": round(max(0, min(100, composite * 0.9 + 5)), 1),
        "sub_scores": scores, "dimensions_valid": n, "dimensions_total": 9,
        "as_of_date": date.today().isoformat(),
    }


def _macro_history(days):
    """按周采样回算历史宏观评分"""
    end = pd.Timestamp.now()
    cursor = end - pd.Timedelta(days=min(days, 365))
    # 找到第一个周五或最近的交易日
    while cursor.dayofweek >= 5:
        cursor += pd.Timedelta(days=1)

    anchors = []
    while cursor <= end:
        anchors.append(cursor)
        cursor += pd.Timedelta(days=7)

    history = []
    for a in anchors:
        c, _, n = _compute(as_of=a)
        if c is not None:
            history.append({"date": a.strftime("%Y-%m-%d"), "score": round(c, 1), "valid_dimensions": n})

    return {
        "indicator": "macro_score", "range": "0-100", "days": days,
        "samples": len(history), "as_of_date": date.today().isoformat(),
        "history": history,
    }


def get_macro_score(days=0):
    if days > 0:
        return _macro_history(days)
    return _macro_latest()
