"""
MarketPulse 共享工具函数

消除各信号模块之间的代码重复：
  - _norm / _rnorm: 线性归一化（10+ 处重复）
  - generate_anchors: 历史回算锚点生成（8+ 处重复）
  - _yoy: 宏观指标同比变化率（2 处重复）
  - _val: 宏观指标取值（1 处独立但供参考）
"""

from typing import Optional
import pandas as pd
from api.day_reader import read_macro_series


# ── 归一化 ──────────────────────────────────────────────────

def norm(v: Optional[float], lo: float, hi: float) -> float:
    """线性归一化到 0-1：v < lo → 0, v > hi → 1, 否则线性映射"""
    if v is None:
        return 0.0
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def rnorm(v: Optional[float], lo: float, hi: float) -> float:
    """反向归一化：1 - norm(v, lo, hi)，用于反向指标（越高越差）"""
    return 1.0 - norm(v, lo, hi)


# ── 历史锚点 ────────────────────────────────────────────────

def generate_anchors(end: pd.Timestamp, days: int,
                     step_days: int = 3, max_points: int = 40,
                     skip_weekends: bool = True) -> list:
    """生成历史回算的时间锚点列表

    Args:
        end: 结束日期（通常是今天）
        days: 回溯天数（自动 min(days, 365)）
        step_days: 采样间隔（天）
        max_points: 最大采样点数
        skip_weekends: 是否跳过周末
    """
    days = min(days, 365)
    cursor = end - pd.Timedelta(days=days)

    anchors = []
    while cursor <= end:
        if not skip_weekends or cursor.dayofweek < 5:
            anchors.append(cursor)
        cursor += pd.Timedelta(days=step_days)

    if len(anchors) > max_points:
        step = max(1, len(anchors) // (max_points - 5))
        anchors = anchors[::step]

    return anchors


# ── 宏观数据辅助 ────────────────────────────────────────────

def yoy(code: str, as_of=None, lag: int = 12) -> Optional[float]:
    """宏观指标同比变化率（%）

    Args:
        code: 宏观指标代码（如 "M2", "CPI"）
        as_of: 指定日期（None=最新）
        lag: 滞后周期数（月频数据用 12）
    """
    try:
        df = read_macro_series(code)
        if as_of is not None:
            df = df[df.index <= pd.Timestamp(as_of)]
        if len(df) < lag + 1:
            return None
        latest = float(df["close"].iloc[-1])
        year_ago = float(df["close"].iloc[-(lag + 1)])
        if year_ago <= 0:
            return None
        return round((latest / year_ago - 1) * 100, 2)
    except Exception:
        return None


def val(code: str, as_of=None, months: int = 3) -> Optional[float]:
    """宏观指标近 N 月均值

    Args:
        code: 宏观指标代码
        as_of: 指定日期（None=最新）
        months: 取最近几个月的均值
    """
    try:
        df = read_macro_series(code)
        if as_of is not None:
            df = df[df.index <= pd.Timestamp(as_of)]
        if len(df) == 0:
            return None
        return float(df["close"].iloc[-months:].mean())
    except Exception:
        return None
