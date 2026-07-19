"""
融资融券情绪分 — 基于两融余额变化判断市场杠杆情绪

指标:
  1. 融资余额 YoY 变化率 — 借钱买入的意愿强度
  2. 融资/融券比值 — 多空力量对比
  3. 融资余额短期趋势 — 近期加杠杆/去杠杆方向

输出: 0-100 分，越高表示杠杆情绪越亢奋（需警惕），越低表示去杠杆/避险

数据来源: 沪深交易所公开两融数据（.day格式存储）
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
from datetime import date
from typing import Optional

from api.day_reader import read_macro_series


def _load_rz() -> Optional[pd.DataFrame]:
    """加载融资余额数据"""
    try:
        return read_macro_series("RZ")
    except Exception:
        return None


def _load_rq() -> Optional[pd.DataFrame]:
    """加载融券余额数据"""
    try:
        return read_macro_series("RQ")
    except Exception:
        return None


def _safe_yoy(df: pd.DataFrame, periods: int = 252) -> Optional[float]:
    """同比变化率——按日历年份对比（±15天窗口内取最接近日）"""
    if df is None or len(df) < 20:
        return None
    latest_date = df.index[-1]
    latest_val = float(df["close"].iloc[-1])

    # 找日历一年前 ±15 天窗口内的数据
    one_year_ago = latest_date - pd.DateOffset(years=1)
    mask = (df.index >= one_year_ago - pd.Timedelta(days=15)) & \
           (df.index <= one_year_ago + pd.Timedelta(days=15))
    nearby = df[mask]

    if len(nearby) == 0:
        if len(df) < periods + 1:
            return None
        past = float(df["close"].iloc[-(periods + 1)])
    else:
        # 取时间差最小的那一天
        diffs = [(abs((d - one_year_ago).days), i) for i, d in enumerate(nearby.index)]
        diffs.sort()
        past = float(nearby["close"].iloc[diffs[0][1]])

    if past <= 0:
        return None
    return round((latest_val / past - 1) * 100, 2)


def _safe_mom_change(df: pd.DataFrame, periods: int = 20) -> Optional[float]:
    """短期变化率（近N日）"""
    if df is None or len(df) < periods + 1:
        return None
    latest = float(df["close"].iloc[-1])
    past = float(df["close"].iloc[-(periods + 1)])
    if past <= 0:
        return None
    return round((latest / past - 1) * 100, 2)


from api.utils import norm as _norm


def _score_rzyoy(yoy: Optional[float]) -> dict:
    """融资余额同比 → 子分数
    融资增速过高 → 杠杆过热 → 高分（警示）
    融资增速为负 → 去杠杆 → 低分
    """
    if yoy is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}
    # -30% ~ +80% 映射到 0-1（覆盖极值情况）
    s = _norm(yoy, -30.0, 80.0)
    return {"value": yoy, "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.35, 4)}


def _score_rzrq_ratio(rz: Optional[pd.DataFrame], rq: Optional[pd.DataFrame]) -> dict:
    """融资/融券比值 → 子分数
    比值越高 → 多头占优 → 高分
    """
    if rz is None or rq is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}
    rz_latest = float(rz["close"].iloc[-1])
    rq_latest = float(rq["close"].iloc[-1])
    if rq_latest <= 0:
        return {"value": None, "sub_score": None, "note": "融券余额为零"}
    ratio = round(rz_latest / rq_latest, 1)
    # 融资/融券 通常在 50-500 之间，映射到 0-1
    s = _norm(ratio, 20.0, 500.0)
    return {"value": ratio, "unit": "倍", "score": round(s, 3), "sub_score": round(s * 0.35, 4)}


def _score_rz_trend(df: Optional[pd.DataFrame]) -> dict:
    """融资余额近20日变化趋势 → 子分数
    持续增加 → 加杠杆 → 高分
    持续减少 → 去杠杆 → 低分
    """
    if df is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}
    mom = _safe_mom_change(df, 20)
    if mom is None:
        return {"value": None, "sub_score": None, "note": "数据不足"}
    # -10% ~ +15% 映射到 0-1
    s = _norm(mom, -10.0, 15.0)
    return {"value": mom, "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.30, 4)}


def _interpret(score: float) -> str:
    if score < 20:
        return "[算法输出] 极度去杠杆——市场极度避险"
    elif score < 35:
        return "[算法输出] 去杠杆中——市场风险偏好低"
    elif score < 50:
        return "[算法输出] 中性偏谨慎——杠杆水平正常偏低"
    elif score < 65:
        return "[算法输出] 中性偏积极——杠杆温和增加"
    elif score < 80:
        return "[算法输出] 加杠杆中——市场风险偏好上升"
    else:
        return "[算法输出] 杠杆过热——需警惕回调风险"


def _margin_history(days: int) -> dict:
    """历史序列（周频采样）— 复用实时评分函数"""
    rz = _load_rz()
    rq = _load_rq()
    if rz is None or rq is None:
        return {"indicator": "margin_sentiment", "status": "no_data", "history": []}

    days = min(days, 365)
    end = pd.Timestamp.now()
    cursor = end - pd.Timedelta(days=days)

    anchors = []
    while cursor <= end:
        if cursor.dayofweek < 5:
            anchors.append(cursor)
        cursor += pd.Timedelta(days=3)

    if len(anchors) > 50:
        step = max(1, len(anchors) // 40)
        anchors = anchors[::step]

    history = []
    for a in anchors:
        try:
            rz_nearby = rz[rz.index <= a]
            rq_nearby = rq[rq.index <= a]
            if len(rz_nearby) < 252 or len(rq_nearby) < 2:
                continue

            rz_yoy = _safe_yoy(rz_nearby, 252)
            s1 = _score_rzyoy(rz_yoy)
            s2 = _score_rzrq_ratio(rz_nearby, rq_nearby)
            s3 = _score_rz_trend(rz_nearby)

            valid = [s["sub_score"] for s in [s1, s2, s3] if s["sub_score"] is not None]
            if not valid:
                continue
            score = round(sum(valid) * 100, 1)

            rz_v = float(rz_nearby["close"].iloc[-1])
            rq_v = float(rq_nearby["close"].iloc[-1])
            ratio = round(rz_v / rq_v, 1) if rq_v > 0 else None

            history.append({
                "date": a.strftime("%Y-%m-%d"),
                "score": score,
                "rz_balance": round(rz_v, 2),
                "rq_balance": round(rq_v, 2),
                "rz_rq_ratio": ratio,
            })
        except Exception:
            continue

    return {
        "indicator": "margin_sentiment", "range": "0-100", "days": days,
        "samples": len(history), "as_of_date": date.today().isoformat(),
        "history": history,
    }


def _compute_margin_at(as_of: pd.Timestamp) -> Optional[float]:
    """在指定日期计算融资融券情绪分 (0-100) — 复用实时评分函数"""
    rz = _load_rz()
    rq = _load_rq()
    if rz is None or rq is None:
        return None

    rz_nearby = rz[rz.index <= as_of]
    rq_nearby = rq[rq.index <= as_of]
    if len(rz_nearby) < 252 or len(rq_nearby) < 2:
        return None

    try:
        rz_yoy = _safe_yoy(rz_nearby, 252)
        s1 = _score_rzyoy(rz_yoy)
        s2 = _score_rzrq_ratio(rz_nearby, rq_nearby)
        s3 = _score_rz_trend(rz_nearby)

        valid = [s["sub_score"] for s in [s1, s2, s3] if s["sub_score"] is not None]
        if not valid:
            return None
        return round(sum(valid) * 100, 1)
    except Exception:
        return None


def get_margin_sentiment(days: int = 0, as_of=None) -> dict:
    """融资融券情绪分 0-100

    Args:
        days: >0 返回历史序列
        as_of: 指定历史日期 (pd.Timestamp 或 date)，计算该日期的值
    """
    if days > 0:
        return _margin_history(days)

    if as_of is not None:
        val = _compute_margin_at(pd.Timestamp(as_of))
        if val is not None:
            return {"indicator": "margin_sentiment", "value": val, "range": "0-100",
                    "interpretation": _interpret(val), "as_of_date": str(as_of)[:10]}
        return {"indicator": "margin_sentiment", "value": None, "status": "no_data",
                "message": "该日期两融数据不足"}

    rz = _load_rz()
    rq = _load_rq()
    if rz is None and rq is None:
        return {"indicator": "margin_sentiment", "value": None, "status": "no_data",
                "message": "两融数据不可用"}

    rzyoy = _safe_yoy(rz)
    rz_trend = _safe_mom_change(rz, 20)

    s1 = _score_rzyoy(rzyoy)
    s2 = _score_rzrq_ratio(rz, rq)
    s3 = _score_rz_trend(rz)

    sub_scores = {"rzyoy": s1, "rzrq_ratio": s2, "rz_trend": s3}
    valid = [s["sub_score"] for s in sub_scores.values() if s["sub_score"] is not None]
    n_valid = len(valid)

    if n_valid == 0:
        return {"indicator": "margin_sentiment", "value": None, "status": "no_data",
                "sub_scores": sub_scores}

    total = round(sum(valid) * 100, 1)  # sub_score 自带权重（0.35+0.35+0.30=1.0）

    rz_latest = float(rz["close"].iloc[-1]) if rz is not None and len(rz) > 0 else None
    rq_latest = float(rq["close"].iloc[-1]) if rq is not None and len(rq) > 0 else None

    return {
        "indicator": "margin_sentiment",
        "value": total,
        "range": "0-100",
        "interpretation": _interpret(total),
        "rz_balance": round(rz_latest, 2) if rz_latest else None,
        "rq_balance": round(rq_latest, 2) if rq_latest else None,
        "rz_yoy_change_pct": rzyoy,
        "rz_trend_20d_pct": rz_trend,
        "sub_scores": sub_scores,
        "dimensions_valid": n_valid,
        "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
