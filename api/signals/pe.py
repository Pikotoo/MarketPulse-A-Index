"""
PE 分位信号 — 全市场估值温度计

计算沪深300 PE的滚动分位值，反映当前估值在历史上的相对位置。

数据来源: 沪深300 PE 历史数据（akshare → 本地 parquet 缓存）
加工深度: 原始PE → 滚动分位计算 → 标准化 0-100 分位值
"""

import pandas as pd
import numpy as np
from datetime import date
from pathlib import Path

from config import PE_CACHE_PATH, PE_LOOKBACK_YEARS


def _load_pe_data() -> pd.DataFrame:
    """加载PE数据（本地 parquet 缓存）"""
    if not PE_CACHE_PATH.exists():
        return None
    df = pd.read_parquet(PE_CACHE_PATH)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def compute_pe_percentile(pe_data: pd.DataFrame,
                          lookback_years: int = None) -> tuple:
    """计算PE当前值和历史分位"""
    if pe_data is None or len(pe_data) == 0:
        return None, None

    if lookback_years is None:
        lookback_years = PE_LOOKBACK_YEARS

    # date 列是 Timestamp，不是 index
    if "date" in pe_data.columns:
        dates = pd.to_datetime(pe_data["date"])
        pe_values = pe_data["pe"]
    else:
        dates = pe_data.index
        pe_values = pe_data["close"] if "close" in pe_data.columns else pe_data.iloc[:, -1]

    latest = pe_data.iloc[-1]
    current_pe = float(latest["pe"]) if "pe" in pe_data.columns else float(latest["close"])

    # 滚动窗口
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_years * 365)
    mask = dates >= cutoff
    historical = pe_values[mask]
    if len(historical) < 100:
        historical = pe_values  # 不够则用全部

    percentile = (historical < current_pe).sum() / len(historical)
    return current_pe, percentile


def _interpret_pe(pct: float) -> str:
    """解读 PE 分位"""
    if pct is None:
        return "未知"
    if pct < 0.20:
        return "极度低估"
    elif pct < 0.35:
        return "低估"
    elif pct < 0.65:
        return "合理"
    elif pct < 0.80:
        return "偏高"
    else:
        return "高估"


def _pe_latest() -> dict:
    """获取最新 PE 信号值"""
    pe_data = _load_pe_data()

    if pe_data is None or len(pe_data) == 0:
        return {
            "indicator": "pe_percentile",
            "value": None,
            "percentile": None,
            "as_of_date": date.today().isoformat(),
            "status": "no_data",
            "message": "PE数据不可用"
        }

    current_pe, pct = compute_pe_percentile(pe_data)

    if current_pe is None:
        return {
            "indicator": "pe_percentile",
            "value": None,
            "percentile": None,
            "as_of_date": date.today().isoformat(),
            "status": "no_data"
        }

    if "date" in pe_data.columns:
        as_of_str = str(pe_data["date"].iloc[-1].date())
    else:
        as_of_str = date.today().isoformat()

    return {
        "indicator": "pe_percentile",
        "value": round(current_pe, 2),
        "percentile": round(pct * 100, 1),
        "range": "0-100",
        "lookback_years": PE_LOOKBACK_YEARS,
        "as_of_date": as_of_str,
        "interpretation": _interpret_pe(pct),
    }


def _pe_history(days: int) -> dict:
    """计算 PE 分位历史序列"""
    pe_data = _load_pe_data()

    if pe_data is None or len(pe_data) == 0:
        return {
            "indicator": "pe_percentile",
            "status": "no_data",
            "history": [],
        }

    if "date" not in pe_data.columns:
        return {
            "indicator": "pe_percentile",
            "status": "error",
            "message": "PE数据格式异常",
            "history": [],
        }

    pe_data["date"] = pd.to_datetime(pe_data["date"])
    pe_data = pe_data.sort_values("date")

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    recent = pe_data[pe_data["date"] >= cutoff]

    if len(recent) == 0:
        return {
            "indicator": "pe_percentile",
            "status": "no_data",
            "message": f"过去 {days} 天无 PE 数据",
            "history": [],
        }

    # 按周聚合（每周最后一个交易日）
    recent["week"] = recent["date"].dt.isocalendar().week.astype(int)
    recent["year"] = recent["date"].dt.isocalendar().year.astype(int)
    weekly = recent.groupby(["year", "week"], sort=True).last().reset_index()

    lookback_days = PE_LOOKBACK_YEARS * 365

    history = []
    for _, row in weekly.iterrows():
        current_date = row["date"]
        current_pe = float(row["pe"])

        # 滚动 N 年分位（截止到当前日期）
        lookback_start = current_date - pd.Timedelta(days=lookback_days)
        hist_window = pe_data[
            (pe_data["date"] >= lookback_start) &
            (pe_data["date"] <= current_date)
        ]
        hist_values = hist_window["pe"]

        if len(hist_values) >= 100:
            pct = round((hist_values < current_pe).sum() / len(hist_values) * 100, 1)
        else:
            pct = None

        history.append({
            "date": str(current_date.date()),
            "pe": round(current_pe, 2),
            "percentile": pct,
            "interpretation": _interpret_pe(pct / 100) if pct is not None else "未知",
        })

    return {
        "indicator": "pe_percentile",
        "range": "0-100",
        "days": days,
        "samples": len(history),
        "lookback_years": PE_LOOKBACK_YEARS,
        "as_of_date": date.today().isoformat(),
        "history": history,
    }


def get_pe_signal(days: int = 0) -> dict:
    """
    PE分位信号

    Args:
        days: 0=返回最新值, >0=返回过去N天的历史序列（周频采样）

    Returns:
        单值模式: value, percentile, lookback_years, interpretation
        历史模式: history[{date, pe, percentile, interpretation}, ...]
    """
    if days > 0:
        return _pe_history(min(days, 365))
    return _pe_latest()
