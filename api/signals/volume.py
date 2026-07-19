"""
量能分 — 基于成交额/成交量的市场活跃度信号

指标:
  1. 成交额偏离度 — 当前成交额 vs 20日均值的偏离程度
  2. 量能趋势 — 5日/20日成交额变化方向
  3. 量价关系 — 放量上涨=健康，缩量下跌=观望

输出: 0-100 分
  <30: 极度缩量（地量）— 市场极度冷清，可能是底部信号
  30-45: 缩量 — 交易清淡
  45-55: 正常 — 量能平稳
  55-70: 放量 — 交易活跃
  70-85: 显著放量 — 市场关注度高，需关注方向
  >85: 天量 — 极度亢奋，需警惕转折

数据来源: 沪深交易所公开成交数据
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


def _load_amount() -> Optional[pd.DataFrame]:
    """加载成交额数据 (TRD = 全市场成交额)"""
    try:
        return read_macro_series("TRD")
    except Exception:
        return None


def _load_volume() -> Optional[pd.DataFrame]:
    """加载成交量数据 (TRL = 全市场成交量)"""
    try:
        return read_macro_series("TRL")
    except Exception:
        return None


def _load_sh_index() -> Optional[pd.DataFrame]:
    """加载上证指数日线（含成交额/量）"""
    try:
        from config import DATA_ROOT
        from api.day_reader import read_day_file
        path = DATA_ROOT / "指数行情" / "上证指数" / "sh000001.day"
        if path.exists():
            return read_day_file(path)
    except Exception:
        pass
    return None


def _norm(v: Optional[float], lo: float, hi: float) -> float:
    """线性归一化到 0-1"""
    if v is None:
        return 0.0
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def _ma_deviation(df: pd.DataFrame, ma_window: int = 20) -> Optional[float]:
    """当前值偏离N日均值的百分比"""
    if df is None or len(df) < ma_window + 1:
        return None
    latest = float(df["close"].iloc[-1])
    ma = float(df["close"].iloc[-ma_window:].mean())
    if ma <= 0:
        return None
    return round((latest / ma - 1) * 100, 2)


def _trend_change(df: pd.DataFrame, window: int = 20) -> Optional[float]:
    """近N日变化率"""
    if df is None or len(df) < window + 1:
        return None
    latest = float(df["close"].iloc[-1])
    past = float(df["close"].iloc[-(window + 1)])
    if past <= 0:
        return None
    return round((latest / past - 1) * 100, 2)


def _vol_price_relation() -> Optional[dict]:
    """量价关系分析：涨放量+跌缩量=健康"""
    try:
        sh = _load_sh_index()
        if sh is None or len(sh) < 22:
            return None

        # 近5日和近20日量价
        for w, label in [(5, "5d"), (20, "20d")]:
            recent = sh.iloc[-w:]
            up_days = recent[recent["close"] > recent["open"]]
            down_days = recent[recent["close"] < recent["open"]]

            up_vol_avg = float(up_days["volume"].mean()) if len(up_days) > 0 else 0
            down_vol_avg = float(down_days["volume"].mean()) if len(down_days) > 0 else 0

            # 涨日量 > 跌日量 = 健康
            if down_vol_avg > 0 and up_vol_avg > 0:
                vp_ratio = round(up_vol_avg / (up_vol_avg + down_vol_avg), 3)
            else:
                vp_ratio = 0.5

        return {"up_vol_ratio": vp_ratio}
    except Exception:
        return None


def _score_amount_deviation(deviation: Optional[float]) -> dict:
    """成交额偏离度 → 子分数
    偏离越大 → 市场越亢奋或恐慌 → 高分（警觉区）
    偏离接近0 → 市场平稳 → 中等分
    极度缩量 → 低分（底部信号，有反转机会）
    """
    if deviation is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}

    # 缩量 < -30% → 低分（地量见地价）
    # 正常 -30% ~ +30% → 中等分
    # 放量 > +30% → 高分（亢奋需警惕）
    abs_dev = abs(deviation)
    if abs_dev < 10:
        s = 0.4  # 正常量能
    elif abs_dev < 20:
        s = 0.5
    elif abs_dev < 30:
        s = 0.6
    elif abs_dev < 50:
        s = 0.75
    else:
        s = 0.9  # 极端放量/缩量

    return {"value": deviation, "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.4, 4)}


def _score_amount_trend(trend_5d: Optional[float], trend_20d: Optional[float]) -> dict:
    """量能趋势 → 子分数
    温和放量 → 高分（市场参与度提升）
    持续缩量 → 低分
    """
    if trend_5d is None and trend_20d is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}

    # 综合短期和中期趋势
    t5 = trend_5d or 0
    t20 = trend_20d or 0
    combined = t5 * 0.6 + t20 * 0.4

    # -20% ~ +30% → 0-1
    s = _norm(combined, -20.0, 30.0)

    return {
        "value": round(combined, 2), "unit": "%",
        "trend_5d": trend_5d, "trend_20d": trend_20d,
        "score": round(s, 3), "sub_score": round(s * 0.35, 4),
    }


def _score_vol_price_health(vp: Optional[dict]) -> dict:
    """量价健康度 → 子分数
    涨放量+跌缩量=健康 → 高分
    涨缩量+跌放量=不健康 → 低分
    """
    if vp is None or vp.get("up_vol_ratio") is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}

    ratio = vp["up_vol_ratio"]
    # ratio > 0.55 = 上涨日成交占比高 = 健康
    # ratio < 0.45 = 下跌日成交占比高 = 不健康
    s = _norm(ratio, 0.35, 0.65)
    return {"value": round(ratio * 100, 1), "unit": "%（涨日成交占比）",
            "score": round(s, 3), "sub_score": round(s * 0.25, 4)}


def _interpret(score: float) -> str:
    if score < 20:
        return "[算法输出] 极度缩量——市场极度冷清，地量或见地价"
    elif score < 35:
        return "[算法输出] 缩量——交易清淡，观望情绪浓厚"
    elif score < 45:
        return "[算法输出] 量能偏低——参与度不足"
    elif score < 55:
        return "[算法输出] 量能正常——市场交投平稳"
    elif score < 65:
        return "[算法输出] 温和放量——市场关注度上升"
    elif score < 80:
        return "[算法输出] 显著放量——资金积极进场"
    else:
        return "[算法输出] 天量——极度亢奋，需警惕转折"


def _volume_history(days: int) -> dict:
    """历史序列"""
    amount = _load_amount()
    sh = _load_sh_index()
    if amount is None and sh is None:
        return {"indicator": "volume_score", "status": "no_data", "history": []}

    # 优先用成交额数据
    df = amount if amount is not None else sh
    if df is None:
        return {"indicator": "volume_score", "status": "no_data", "history": []}

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
            nearby = df[df.index <= a]
            if len(nearby) < 22:
                continue

            ma20 = float(nearby["close"].iloc[-20:].mean())
            latest = float(nearby["close"].iloc[-1])
            dev = round((latest / ma20 - 1) * 100, 2) if ma20 > 0 else 0

            # 简化的趋势
            if len(nearby) >= 6:
                t5_latest = float(nearby["close"].iloc[-1])
                t5_past = float(nearby["close"].iloc[-6])
                t5 = round((t5_latest / t5_past - 1) * 100, 2) if t5_past > 0 else 0
            else:
                t5 = 0

            abs_dev = abs(dev)
            if abs_dev < 10: s = 0.4
            elif abs_dev < 20: s = 0.5
            elif abs_dev < 30: s = 0.6
            elif abs_dev < 50: s = 0.75
            else: s = 0.9

            s_trend = _norm(t5, -20.0, 30.0)
            score = round((s * 0.5 + s_trend * 0.5) * 100, 1)

            history.append({
                "date": a.strftime("%Y-%m-%d"),
                "score": score,
                "amount_latest": round(latest, 2),
                "amount_ma20": round(ma20, 2),
                "deviation_pct": dev,
            })
        except Exception:
            continue

    return {
        "indicator": "volume_score", "range": "0-100", "days": days,
        "samples": len(history), "as_of_date": date.today().isoformat(),
        "history": history,
    }


def _compute_volume_at(as_of: pd.Timestamp) -> Optional[float]:
    """在指定日期计算量能分 (0-100)"""
    amount = _load_amount()
    if amount is None:
        return None

    nearby = amount[amount.index <= as_of]
    if len(nearby) < 22:
        return None

    try:
        ma20 = float(nearby["close"].iloc[-20:].mean())
        latest = float(nearby["close"].iloc[-1])
        dev = round((latest / ma20 - 1) * 100, 2) if ma20 > 0 else 0

        if len(nearby) >= 6:
            t5_latest = float(nearby["close"].iloc[-1])
            t5_past = float(nearby["close"].iloc[-6])
            t5 = round((t5_latest / t5_past - 1) * 100, 2) if t5_past > 0 else 0
        else:
            t5 = 0

        abs_dev = abs(dev)
        if abs_dev < 10: s_dev = 0.4
        elif abs_dev < 20: s_dev = 0.5
        elif abs_dev < 30: s_dev = 0.6
        elif abs_dev < 50: s_dev = 0.75
        else: s_dev = 0.9

        s_trend = _norm(t5, -20.0, 30.0)

        # 简化：量价关系权重降低（历史难以精确计算），偏差+趋势各半
        return round((s_dev * 0.5 + s_trend * 0.5) * 100, 1)
    except Exception:
        return None


def get_volume_score(days: int = 0, as_of=None) -> dict:
    """量能分 0-100

    Args:
        days: >0 返回历史序列
        as_of: 指定历史日期 (pd.Timestamp 或 date)，计算该日期的值
    """
    if days > 0:
        return _volume_history(days)

    if as_of is not None:
        val = _compute_volume_at(pd.Timestamp(as_of))
        if val is not None:
            return {"indicator": "volume_score", "value": val, "range": "0-100",
                    "interpretation": _interpret(val), "as_of_date": str(as_of)[:10]}
        return {"indicator": "volume_score", "value": None, "status": "no_data",
                "message": "该日期量能数据不足"}

    amount = _load_amount()
    dev = _ma_deviation(amount, 20)

    trend5 = _trend_change(amount, 5)
    trend20 = _trend_change(amount, 20)

    vp = _vol_price_relation()

    s1 = _score_amount_deviation(dev)
    s2 = _score_amount_trend(trend5, trend20)
    s3 = _score_vol_price_health(vp)

    sub_scores = {"amount_deviation": s1, "amount_trend": s2, "vol_price_health": s3}
    valid = [s["sub_score"] for s in sub_scores.values() if s["sub_score"] is not None]
    n_valid = len(valid)

    if n_valid == 0:
        return {"indicator": "volume_score", "value": None, "status": "no_data",
                "sub_scores": sub_scores}

    total = round(sum(valid) / n_valid * 3 * 100, 1)

    amt_latest = float(amount["close"].iloc[-1]) if amount is not None and len(amount) > 0 else None

    return {
        "indicator": "volume_score",
        "value": total,
        "range": "0-100",
        "interpretation": _interpret(total),
        "amount_latest": round(amt_latest, 2) if amt_latest else None,
        "deviation_ma20_pct": dev,
        "trend_5d_pct": trend5,
        "trend_20d_pct": trend20,
        "vol_price_health": vp,
        "sub_scores": sub_scores,
        "dimensions_valid": n_valid,
        "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
