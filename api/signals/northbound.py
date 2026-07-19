"""
北向资金情绪分 — 基于沪深港通北向资金净流向的市场情绪信号

数据特征: TRNBD 为月度累计净买入额，~118条记录覆盖2016-2026
指标 (3维):
  1. 近月净流向 — 最近1个月净买入额
  2. 季度趋势 — 近3个月累计 vs 过去12个月均值
  3. 流入持续性 — 连续净流入月数

输出: 0-100 分
  <25: 持续流出——外资撤离
  25-40: 偏流出——外资谨慎
  40-55: 中性——进出平衡
  55-70: 偏流入——外资温和加仓
  70-85: 持续流入——外资积极看多
  >85: 爆买——短期外资过热

数据来源: 沪深港通公开交易数据
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional

from api.day_reader import read_macro_series


def _load_northbound() -> Optional[pd.DataFrame]:
    """加载北向资金数据 (TRNBD = 月度累计净买入)"""
    try:
        return read_macro_series("TRNBD")
    except Exception:
        return None


def _monthly_flows(df: pd.DataFrame) -> Optional[pd.Series]:
    """月度净流入（diff of cumulative）"""
    if df is None or len(df) < 2:
        return None
    return df["close"].diff().dropna()


def _norm(v: Optional[float], lo: float, hi: float) -> float:
    if v is None:
        return 0.0
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def _percentile_rank(series: pd.Series, value: float) -> float:
    """计算 value 在历史序列中的百分位排名 → 0-1"""
    if series is None or len(series) < 10:
        return 0.5
    return round((series < value).sum() / len(series), 3)


def _score_recent_flow(flows: pd.Series) -> dict:
    """近1个月净流向 → 百分位排名 (权重 0.35)"""
    if flows is None or len(flows) < 2:
        return {"value": None, "sub_score": None, "note": "数据不可用"}

    latest = float(flows.iloc[-1])
    pct_rank = _percentile_rank(flows, latest)

    return {
        "value": round(latest, 1), "unit": "（月度净买入）",
        "percentile": round(pct_rank * 100, 1),
        "score": round(pct_rank, 3),
        "sub_score": round(pct_rank * 0.35, 4),
    }


def _score_quarterly_trend(flows: pd.Series) -> dict:
    """近3月累计 vs 12月均值 → 趋势强度 (权重 0.35)"""
    if flows is None or len(flows) < 12:
        return {"value": None, "sub_score": None, "note": "数据不足"}

    q3_total = float(flows.iloc[-3:].sum())
    y12_avg = float(flows.iloc[-12:].mean())

    if y12_avg == 0:
        return {"value": None, "sub_score": None}

    # 近3月总流入 vs 月均流入的倍数
    ratio = round(q3_total / (abs(y12_avg) * 3), 2) if y12_avg != 0 else 1.0

    # ratio > 1.5 = 加速流入，ratio < 0 = 转为净流出
    s = _norm(ratio, -1.0, 2.5)
    return {
        "value": round(q3_total, 1), "unit": "（近3月累计）",
        "q3_total": q3_total, "monthly_avg_12m": round(y12_avg, 1),
        "score": round(s, 3),
        "sub_score": round(s * 0.35, 4),
    }


def _score_continuity(flows: pd.Series) -> dict:
    """连续净流入月数 (权重 0.30)"""
    if flows is None or len(flows) < 1:
        return {"value": None, "sub_score": None, "note": "数据不可用"}

    latest = float(flows.iloc[-1])
    count = 0
    direction = 1 if latest > 0 else -1
    for i in range(len(flows) - 1, -1, -1):
        val = float(flows.iloc[i])
        if (direction > 0 and val > 0) or (direction < 0 and val < 0):
            count += 1
        else:
            break

    cons = count * direction
    abs_cons = abs(cons)

    if abs_cons <= 1:
        s = 0.45
    elif abs_cons <= 3:
        s = 0.25 if cons < 0 else 0.60
    elif abs_cons <= 6:
        s = 0.10 if cons < 0 else 0.75
    elif abs_cons <= 12:
        s = 0.03 if cons < 0 else 0.88
    else:
        s = 0.0 if cons < 0 else 0.95

    direction_label = "流入" if cons > 0 else "流出"
    return {
        "value": cons, "unit": f"个月（连续{direction_label}）",
        "consecutive_months": abs_cons,
        "direction": direction_label,
        "score": round(s, 3),
        "sub_score": round(s * 0.30, 4),
    }


def _interpret(score: float) -> str:
    if score < 20:
        return "[算法输出] 外资持续流出——市场极度悲观"
    elif score < 35:
        return "[算法输出] 外资偏流出——境外资金谨慎"
    elif score < 45:
        return "[算法输出] 外资中性偏空——小幅净流出"
    elif score < 55:
        return "[算法输出] 外资中性——进出基本平衡"
    elif score < 65:
        return "[算法输出] 外资中性偏多——小幅净流入"
    elif score < 80:
        return "[算法输出] 外资持续流入——境外资金积极看多"
    else:
        return "[算法输出] 外资爆买——短期情绪过热"


def _northbound_history(days: int) -> dict:
    """历史序列（月频采样）"""
    df = _load_northbound()
    if df is None:
        return {"indicator": "northbound_sentiment", "status": "no_data", "history": []}

    flows = _monthly_flows(df)
    if flows is None or len(flows) < 3:
        return {"indicator": "northbound_sentiment", "status": "no_data", "history": []}

    # 月频采样：每个月一个点
    history = []
    for idx in range(12, len(flows)):
        try:
            window = flows.iloc[:idx + 1]
            latest = float(window.iloc[-1])
            pct_rank = _percentile_rank(window, latest)

            q3 = float(window.iloc[-3:].sum()) if len(window) >= 3 else 0
            y12_avg = float(window.iloc[-12:].mean()) if len(window) >= 12 else float(window.mean())
            ratio = round(q3 / (abs(y12_avg) * 3 + 1), 2)
            s_trend = _norm(ratio, -1.0, 2.5)

            cons = 0
            direction = 1 if latest > 0 else -1
            for j in range(len(window) - 1, -1, -1):
                val = float(window.iloc[j])
                if (direction > 0 and val > 0) or (direction < 0 and val < 0):
                    cons += 1
                else:
                    break
            cons = cons * direction
            abs_cons = abs(cons)
            if abs_cons <= 1: s_cons = 0.45
            elif abs_cons <= 3: s_cons = 0.25 if cons < 0 else 0.60
            elif abs_cons <= 6: s_cons = 0.10 if cons < 0 else 0.75
            elif abs_cons <= 12: s_cons = 0.03 if cons < 0 else 0.88
            else: s_cons = 0.0 if cons < 0 else 0.95

            score = round((pct_rank * 0.35 + s_trend * 0.35 + s_cons * 0.30) * 100, 1)
            dt = flows.index[idx]
            history.append({
                "date": dt.strftime("%Y-%m-%d"),
                "score": score,
                "monthly_flow": round(latest, 1),
                "consecutive_months": cons,
            })
        except Exception:
            continue

    return {
        "indicator": "northbound_sentiment", "range": "0-100",
        "samples": len(history), "as_of_date": date.today().isoformat(),
        "note": "月频数据，历史序列为逐月回算",
        "history": history,
    }


def _compute_northbound_at(as_of: pd.Timestamp) -> Optional[float]:
    """在指定日期计算北向资金情绪分 (0-100)"""
    df = _load_northbound()
    if df is None:
        return None

    df_nearby = df[df.index <= as_of]
    if len(df_nearby) < 14:
        return None

    try:
        flows = _monthly_flows(df_nearby)
        if flows is None or len(flows) < 3:
            return None

        latest = float(flows.iloc[-1])
        pct_rank = _percentile_rank(flows, latest)

        q3 = float(flows.iloc[-3:].sum()) if len(flows) >= 3 else 0
        y12_avg = float(flows.iloc[-12:].mean()) if len(flows) >= 12 else float(flows.mean())
        ratio = round(q3 / (abs(y12_avg) * 3 + 1), 2)
        s_trend = _norm(ratio, -1.0, 2.5)

        cons = 0
        direction = 1 if latest > 0 else -1
        for j in range(len(flows) - 1, -1, -1):
            val = float(flows.iloc[j])
            if (direction > 0 and val > 0) or (direction < 0 and val < 0):
                cons += 1
            else:
                break
        cons = cons * direction
        abs_cons = abs(cons)
        if abs_cons <= 1: s_cons = 0.45
        elif abs_cons <= 3: s_cons = 0.25 if cons < 0 else 0.60
        elif abs_cons <= 6: s_cons = 0.10 if cons < 0 else 0.75
        elif abs_cons <= 12: s_cons = 0.03 if cons < 0 else 0.88
        else: s_cons = 0.0 if cons < 0 else 0.95

        return round((pct_rank * 0.35 + s_trend * 0.35 + s_cons * 0.30) * 100, 1)
    except Exception:
        return None


def get_northbound_sentiment(days: int = 0, as_of=None) -> dict:
    """北向资金情绪分 0-100

    Args:
        days: >0 返回历史序列
        as_of: 指定历史日期 (pd.Timestamp 或 date)，计算该日期的值
    """
    if days > 0:
        return _northbound_history(days)

    if as_of is not None:
        val = _compute_northbound_at(pd.Timestamp(as_of))
        if val is not None:
            return {"indicator": "northbound_sentiment", "value": val, "range": "0-100",
                    "interpretation": _interpret(val), "as_of_date": str(as_of)[:10]}
        return {"indicator": "northbound_sentiment", "value": None, "status": "no_data",
                "message": "该日期北向资金数据不足"}

    df = _load_northbound()
    if df is None:
        return {"indicator": "northbound_sentiment", "value": None, "status": "no_data",
                "message": "北向资金数据不可用"}

    flows = _monthly_flows(df)
    if flows is None or len(flows) < 3:
        return {"indicator": "northbound_sentiment", "value": None, "status": "no_data",
                "message": "北向资金数据不足"}

    s1 = _score_recent_flow(flows)
    s2 = _score_quarterly_trend(flows)
    s3 = _score_continuity(flows)

    sub_scores = {"recent_flow": s1, "quarterly_trend": s2, "continuity": s3}
    valid = [s["sub_score"] for s in sub_scores.values() if s["sub_score"] is not None]
    n_valid = len(valid)

    if n_valid == 0:
        return {"indicator": "northbound_sentiment", "value": None, "status": "no_data",
                "sub_scores": sub_scores}

    total = round(sum(valid) / n_valid * 3 * 100, 1)

    return {
        "indicator": "northbound_sentiment",
        "value": total,
        "range": "0-100",
        "interpretation": _interpret(total),
        "flow_latest_month": round(float(flows.iloc[-1]), 1) if len(flows) > 0 else None,
        "sub_scores": sub_scores,
        "dimensions_valid": n_valid,
        "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
