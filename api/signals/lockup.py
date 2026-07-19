"""
限售解禁压力分 — 基于已发生解禁成交量 + 可选未来解禁预测

指标:
  1. 解禁成交量偏离度 — 近5日解禁量 vs 20日均值的偏离
  2. 解禁量趋势 — 近20日解禁量的变化方向
  3. 解禁占成交比 — 解禁量占市场总成交的比例

输出: 0-100 分，越高=解禁压力越大（对市场偏负面）
  <20: 解禁压力极低
  20-40: 解禁压力较低
  40-55: 解禁压力正常
  55-70: 解禁压力偏高
  70-85: 解禁压力较大——供给增加需关注
  >85: 解禁洪峰——大量流通盘释放

数据来源: 沪深交易所公开数据 (ScJyData_zbca.csv)
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
from datetime import date
from typing import Optional

from config import DATA_ROOT

_CSV_PATH = DATA_ROOT / "市场指标" / "ScJyData_zbca.csv"


def _load_lockup() -> Optional[pd.DataFrame]:
    """加载限售解禁数据 (SZG34_VOL + XDG34_VOL)"""
    if not _CSV_PATH.exists():
        return None
    try:
        df = pd.read_csv(_CSV_PATH)
        df["date"] = pd.to_datetime(df["date"], format="%Y_%m_%d")
        df = df.set_index("date").sort_index()
        # 合并沪深解禁量
        vols = []
        if "SZG34_VOL" in df.columns:
            vols.append(df["SZG34_VOL"])
        if "XDG34_VOL" in df.columns:
            vols.append(df["XDG34_VOL"])

        if not vols:
            return None

        result = pd.DataFrame({"total_lockup_vol": sum(vols)}, index=df.index)
        return result
    except Exception:
        return None


from api.utils import norm as _norm


def _vol_deviation(df: pd.DataFrame, ma_window: int = 20) -> Optional[float]:
    """当前解禁量偏离N日均值的百分比"""
    if df is None or len(df) < ma_window + 1:
        return None
    latest = float(df["total_lockup_vol"].iloc[-1])
    ma = float(df["total_lockup_vol"].iloc[-ma_window:].mean())
    if ma <= 0:
        return None
    return round((latest / ma - 1) * 100, 2)


def _trend_change(df: pd.DataFrame, window: int = 20) -> Optional[float]:
    """近N日变化率"""
    if df is None or len(df) < window + 1:
        return None
    latest_ma5 = float(df["total_lockup_vol"].iloc[-5:].mean())
    past_ma5 = float(df["total_lockup_vol"].iloc[-(window + 5):-window].mean())
    if past_ma5 <= 0:
        return None
    return round((latest_ma5 / past_ma5 - 1) * 100, 2)


def _score_deviation(deviation: Optional[float]) -> dict:
    """解禁量偏离度 → 子分数 (0.40)"""
    if deviation is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}
    # 偏离越大 → 压力越大
    s = _norm(deviation, -30.0, 100.0)
    return {"value": deviation, "unit": "%（vs MA20）",
            "score": round(s, 3), "sub_score": round(s * 0.40, 4)}


def _score_trend(trend: Optional[float]) -> dict:
    """解禁量趋势 → 子分数 (0.30)"""
    if trend is None:
        return {"value": None, "sub_score": None, "note": "数据不可用"}
    # 上升趋势 → 压力增大
    s = _norm(trend, -30.0, 80.0)
    return {"value": trend, "unit": "%（20日变化）",
            "score": round(s, 3), "sub_score": round(s * 0.30, 4)}


def _score_ratio(df: pd.DataFrame) -> dict:
    """解禁量120日均值 → 用于衡量结构性的解禁供应（0.30）"""
    if df is None or len(df) < 120:
        return {"value": None, "sub_score": None, "note": "数据不足"}
    ma20 = float(df["total_lockup_vol"].iloc[-20:].mean())
    ma120 = float(df["total_lockup_vol"].iloc[-120:].mean())
    if ma120 <= 0:
        return {"value": None, "sub_score": None, "note": "数据不可用"}

    ratio = round(ma20 / ma120, 2)
    # ratio > 1.5 → 近期解禁显著高于历史平均
    s = _norm(ratio, 0.5, 2.5)
    return {"value": ratio, "unit": "倍（vs 半年均值）",
            "score": round(s, 3), "sub_score": round(s * 0.30, 4)}


def _interpret(score: float) -> str:
    if score < 20:
        return "[算法输出] 解禁压力极低——流通盘供给稳定"
    elif score < 35:
        return "[算法输出] 解禁压力较低——市场承接力充足"
    elif score < 50:
        return "[算法输出] 解禁压力正常——供给节奏平稳"
    elif score < 65:
        return "[算法输出] 解禁压力偏高——关注个股解禁窗口"
    elif score < 80:
        return "[算法输出] 解禁压力较大——流通盘供给增加，需关注承接力"
    else:
        return "[算法输出] 解禁洪峰——大量筹码解禁释放"


def _lockup_history(days: int) -> dict:
    """历史序列 — 使用与实时模式一致的 3 维评分（偏离+趋势+历史比值）"""
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
            result = _compute_lockup_at(a)
            if result is not None:
                history.append({
                    "date": a.strftime("%Y-%m-%d"),
                    "score": result["value"],
                })
        except Exception:
            continue

    return {
        "indicator": "lockup_pressure", "range": "0-100", "days": days,
        "samples": len(history), "as_of_date": date.today().isoformat(),
        "history": history,
    }


def _compute_lockup_at(as_of: pd.Timestamp) -> Optional[dict]:
    """在指定日期计算限售解禁压力分 — 与实时模式使用相同的 3 维评分"""
    df = _load_lockup()
    if df is None:
        return None

    nearby = df[df.index <= pd.Timestamp(as_of)]
    if len(nearby) < 22:
        return None

    try:
        dev = _vol_deviation(nearby)
        trend = _trend_change(nearby)

        s1 = _score_deviation(dev)
        s2 = _score_trend(trend)
        s3 = _score_ratio(nearby)

        valid = [s["sub_score"] for s in [s1, s2, s3] if s["sub_score"] is not None]
        if not valid:
            return None

        total = round(sum(valid) * 100, 1)
        return {
            "indicator": "lockup_pressure", "value": total, "range": "0-100",
            "interpretation": _interpret(total),
            "sub_scores": {"volume_deviation": s1, "trend": s2, "vs_historical_ratio": s3},
            "dimensions_valid": len(valid), "dimensions_total": 3,
            "as_of_date": str(as_of)[:10],
        }
    except Exception:
        return None


def get_lockup_pressure(days: int = 0, as_of=None) -> dict:
    """限售解禁压力分 0-100

    Args:
        days: >0 返回历史序列
        as_of: 指定历史日期 (pd.Timestamp 或 date)，计算该日期的值
    """
    if days > 0:
        return _lockup_history(days)

    if as_of is not None:
        result = _compute_lockup_at(pd.Timestamp(as_of))
        if result is not None:
            return result
        return {"indicator": "lockup_pressure", "value": None, "status": "no_data",
                "message": "该日期解禁数据不足"}

    df = _load_lockup()
    if df is None:
        return {"indicator": "lockup_pressure", "value": None, "status": "no_data",
                "message": "限售解禁数据不可用（需 ScJyData_zbca.csv）"}

    dev = _vol_deviation(df)
    trend = _trend_change(df)
    ratio_info = _score_ratio(df)

    s1 = _score_deviation(dev)
    s2 = _score_trend(trend)
    s3 = ratio_info

    sub_scores = {"volume_deviation": s1, "trend": s2, "vs_historical_ratio": s3}
    valid = [s["sub_score"] for s in sub_scores.values() if s["sub_score"] is not None]
    n_valid = len(valid)

    if n_valid == 0:
        return {"indicator": "lockup_pressure", "value": None, "status": "no_data",
                "sub_scores": sub_scores}

    total = round(sum(valid) * 100, 1)  # sub_score 自带权重（0.40+0.30+0.30=1.0）

    latest_vol = float(df["total_lockup_vol"].iloc[-1]) if len(df) > 0 else None

    return {
        "indicator": "lockup_pressure",
        "value": total,
        "range": "0-100",
        "interpretation": _interpret(total),
        "lockup_vol_latest": round(latest_vol, 2) if latest_vol else None,
        "data_source": "已发生解禁成交量（沪深合计），非未来解禁预测",
        "sub_scores": sub_scores,
        "dimensions_valid": n_valid,
        "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
