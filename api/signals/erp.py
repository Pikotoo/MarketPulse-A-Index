"""
股权风险溢价 (ERP) — 股债性价比指标

ERP = 1/PE - 10年国债收益率

当 ERP 高 → 股票相对债券更便宜 → 配置价值高
当 ERP 低 → 股票相对债券偏贵 → 债券更具吸引力

数据来源: 中证指数公司、中债登
加工深度: PE → 倒数 → 扣除无风险利率 → 标准化分位 → 股债性价比分数
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
from datetime import date
from typing import Optional

from config import PE_LOOKBACK_YEARS
from api.day_reader import read_macro_series, get_macro_value
from api.signals.pe import compute_pe_percentile, _load_pe_data


def _get_bond_yield(code: str = "CNG10Y") -> Optional[float]:
    """获取10年期国债收益率"""
    try:
        val = get_macro_value(code)
        if val is not None:
            return val
    except Exception:
        pass

    # 尝试其他代码
    for alt in ["CNDT10Y", "CNT10Y", "CNDTFY"]:
        try:
            val = get_macro_value(alt)
            if val is not None:
                return val
        except Exception:
            continue

    return None


def _compute_erp(pe: float, bond_yield: float) -> float:
    """计算 ERP = 1/PE - 10Y国债收益率"""
    if pe <= 0 or bond_yield <= 0:
        return None
    earnings_yield = 1.0 / pe * 100  # 市盈率倒数，百分比
    return round(earnings_yield - bond_yield, 3)


def _interpret_erp(pct: Optional[float]) -> str:
    """解读 ERP — 基于分位而非绝对值"""
    if pct is None:
        return "未知"
    if pct < 15:
        return "债券极具优势——ERP处于历史低位，股票相对昂贵"
    elif pct < 30:
        return "债券较有优势——ERP偏低，债券性价比更高"
    elif pct < 45:
        return "债券略占优——ERP中等偏低"
    elif pct < 55:
        return "股债均衡——ERP处于历史中位"
    elif pct < 70:
        return "股票略占优——ERP中等偏高"
    elif pct < 85:
        return "股票较有吸引力——ERP偏高"
    else:
        return "股票极具吸引力——ERP处于历史高位"


def _erp_percentile(current_erp: float, pe_data, bond_yield: float) -> Optional[float]:
    """计算 ERP 的真实历史分位

    用 PE 历史数据 + 当前国债收益率，在回溯窗口内逐日重算 ERP，
    然后计算当前 ERP 在这些历史值中的分位。
    """
    if pe_data is None or len(pe_data) == 0 or current_erp is None or bond_yield is None:
        return None

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=PE_LOOKBACK_YEARS * 365)
    if "date" in pe_data.columns:
        pe_data["date"] = pd.to_datetime(pe_data["date"])
        hist = pe_data[pe_data["date"] >= cutoff]
    else:
        hist = pe_data.iloc[-PE_LOOKBACK_YEARS * 250:]  # 约250交易日/年

    if len(hist) < 50:
        return None

    erp_values = []
    for _, row in hist.iterrows():
        pe = float(row["pe"])
        e = _compute_erp(pe, bond_yield)
        if e is not None:
            erp_values.append(e)

    if not erp_values:
        return None

    pct = round((sum(1 for e in erp_values if e < current_erp) / len(erp_values)) * 100, 1)
    return pct


def _erp_latest() -> dict:
    """获取最新 ERP 信号值"""
    try:
        pe_data = _load_pe_data()
        current_pe, _ = compute_pe_percentile(pe_data)
    except Exception:
        current_pe = None

    bond_yield = _get_bond_yield()

    if current_pe is None and bond_yield is None:
        return {
            "indicator": "erp",
            "value": None,
            "status": "no_data",
            "message": "PE和国债数据均不可用",
        }

    if current_pe is None:
        return {
            "indicator": "erp",
            "value": None,
            "status": "partial",
            "message": "PE数据不可用",
            "bond_yield_10y": round(bond_yield, 3) if bond_yield else None,
        }

    if bond_yield is None:
        return {
            "indicator": "erp",
            "value": None,
            "status": "partial",
            "message": "国债收益率数据不可用",
            "pe": round(current_pe, 2),
            "earnings_yield": round(1.0 / current_pe * 100, 3),
        }

    earnings_yield = 1.0 / current_pe * 100
    erp = _compute_erp(current_pe, bond_yield)

    if erp is None:
        return {
            "indicator": "erp",
            "value": None,
            "status": "error",
            "message": "ERP计算异常",
        }

    pct = _erp_percentile(erp, pe_data, bond_yield)

    return {
        "indicator": "erp",
        "value": erp,
        "unit": "%",
        "range": "typically -2 to +8",
        "pe": round(current_pe, 2),
        "earnings_yield": round(earnings_yield, 3),
        "bond_yield_10y": round(bond_yield, 3),
        "percentile": pct,
        "interpretation": _interpret_erp(pct),
        "as_of_date": date.today().isoformat(),
    }


def _get_bond_yield_at(as_of: pd.Timestamp) -> Optional[float]:
    """获取指定日期的 10 年国债收益率（从历史 .day 文件中读取）"""
    for code in ["CNG10Y", "CNDT10Y", "CNT10Y", "CNDTFY"]:
        try:
            df = read_macro_series(code)
            if df is None or len(df) == 0:
                continue
            nearby = df[df.index <= as_of]
            if len(nearby) > 0:
                return float(nearby["close"].iloc[-1])
        except Exception:
            continue
    return None


def _erp_history(days: int) -> dict:
    """计算 ERP 历史序列（周频采样，使用历史债券收益率）"""
    pe_data = _load_pe_data()
    if pe_data is None or len(pe_data) == 0:
        return {
            "indicator": "erp",
            "status": "no_data",
            "history": [],
        }

    if "date" not in pe_data.columns:
        return {
            "indicator": "erp",
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
            "indicator": "erp",
            "status": "no_data",
            "message": f"过去 {days} 天无 PE 数据",
            "history": [],
        }

    # 按周采样（每周最后一个交易日）
    recent["week"] = recent["date"].dt.isocalendar().week.astype(int)
    recent["year"] = recent["date"].dt.isocalendar().year.astype(int)
    weekly = recent.groupby(["year", "week"], sort=True).last().reset_index()

    # 预加载债券收益率历史（避免逐行重复读文件）
    bond_history = None
    for code in ["CNG10Y", "CNDT10Y", "CNT10Y", "CNDTFY"]:
        try:
            bond_history = read_macro_series(code)
            if bond_history is not None and len(bond_history) > 0:
                break
        except Exception:
            continue

    history = []
    bond_fallback = _get_bond_yield()  # 最新值作为兜底
    for _, row in weekly.iterrows():
        pe = float(row["pe"])
        dt = row["date"]
        dt_str = str(dt.date())

        # 使用该日期的债券收益率（而非最新值）
        bond_yield = None
        if bond_history is not None:
            bond_nearby = bond_history[bond_history.index <= dt]
            if len(bond_nearby) > 0:
                bond_yield = float(bond_nearby["close"].iloc[-1])
        if bond_yield is None:
            bond_yield = bond_fallback  # 历史数据不可用时用最新值兜底

        if bond_yield:
            erp = _compute_erp(pe, bond_yield)
            if erp is not None:
                history.append({
                    "date": dt_str,
                    "erp": erp,
                    "pe": round(pe, 2),
                    "bond_yield": round(bond_yield, 3),
                })

    return {
        "indicator": "erp",
        "unit": "%",
        "days": days,
        "samples": len(history),
        "as_of_date": date.today().isoformat(),
        "note": "ERP历史使用对应日期的债券收益率（非固定最新值）",
        "history": history,
    }


def get_erp_signal(days: int = 0) -> dict:
    """
    股权风险溢价信号

    Args:
        days: 0=返回最新值, >0=返回过去N天的历史序列（周频采样）

    Returns:
        单值模式: erp_value, pe, earnings_yield, bond_yield, percentile, interpretation
        历史模式: history[{date, erp, pe}, ...]
    """
    if days > 0:
        return _erp_history(min(days, 365))
    return _erp_latest()
