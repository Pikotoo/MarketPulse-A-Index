"""
综合情绪分 — 7 维度等权合成 0-100

输入 (v2.1):
  PE 分位（反转）   × 1/7    — 估值越低分数越高
  ERP               × 1/7    — ERP 越高分数越高
  宏观评分           × 1/7    — 直接使用（9维）
  行业宽度           × 1/7    — 宽度越高分数越高
  融资融券情绪       × 1/7    — [v2.1] 杠杆情绪
  北向资金情绪       × 1/7    — [v2.1] 外资流向
  量能分             × 1/7    — [v2.1] 交投活跃度

输出: 0-100 单一分数，辅助判断市场整体冷热

历史模式（days>0）: 对每个采样点逐日回算核心 4 维度的真实值。
ERP 维度受限于无历史国债收益率，使用当天债券利率 + 历史 PE 计算。
新增维度（margin/northbound/volume）在历史模式中也逐点回算。
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
import numpy as np
from datetime import date
from typing import Optional

from api.day_reader import get_macro_value


def _score_pe(pct: Optional[float]) -> Optional[float]:
    """PE 分位 → 情绪子分（反转）"""
    if pct is None:
        return None
    return float(round((100 - float(pct)) * 0.1429, 1))  # 1/7


def _score_erp_value(erp: Optional[float]) -> Optional[float]:
    """ERP → 情绪子分（映射 -2~+8 → 0-100）"""
    if erp is None:
        return None
    normalized = max(0, min(100, (float(erp) + 2) / 8 * 100))
    return float(round(normalized * 0.1429, 1))  # 1/7


def _compute_erp_from_pe(pe: float, bond_yield: float = None) -> Optional[float]:
    """从 PE 和债券收益率计算 ERP"""
    if pe <= 0:
        return None
    if bond_yield is None:
        bond_yield = _get_bond_yield_latest()
    if bond_yield is None:
        return None
    return round(1.0 / pe * 100 - bond_yield, 3)


def _get_bond_yield_latest() -> Optional[float]:
    """获取最新 10 年国债收益率"""
    for code in ["CNG10Y", "CNDT10Y", "CNT10Y", "CNDTFY"]:
        try:
            v = get_macro_value(code)
            if v is not None:
                return v
        except Exception:
            continue
    return None


def _score_erp() -> Optional[float]:
    """获取最新 ERP 情绪分"""
    try:
        from api.signals.erp import get_erp_signal
        result = get_erp_signal(days=0)
        erp = result.get("value")
        return _score_erp_value(erp)
    except Exception:
        pass
    return None


def _score_macro(as_of: Optional[pd.Timestamp] = None) -> Optional[float]:
    """宏观评分 → 情绪子分（支持历史回算）"""
    try:
        from api.signals.macro_score import _compute as macro_compute
        composite, _, _ = macro_compute(as_of=as_of)
        if composite is not None:
            return float(round(float(composite) * 0.1429, 1))  # 1/7
    except Exception:
        pass
    return None


def _score_breadth(as_of: Optional[pd.Timestamp] = None) -> Optional[float]:
    """行业宽度 → 情绪子分（支持历史回算）"""
    try:
        from api.signals.sector import get_sector_breadth
        dt = as_of.date() if as_of else None
        result = get_sector_breadth(dt=dt, days=0)
        val = result.get("value")
        if val is not None:
            return float(round(float(val) * 100 * 0.1429, 1))  # 1/7
    except Exception:
        pass
    return None


# ── v2.1 新增维度 ──────────────────────────────────────────

def _score_margin(as_of=None) -> Optional[float]:
    """融资融券情绪 → 情绪子分（支持历史日期）"""
    try:
        from api.signals.margin import get_margin_sentiment
        result = get_margin_sentiment(days=0, as_of=as_of)
        val = result.get("value")
        if val is not None:
            return float(round(float(val) * 0.1429, 1))  # 1/7
    except Exception:
        pass
    return None


def _score_northbound(as_of=None) -> Optional[float]:
    """北向资金情绪 → 情绪子分（支持历史日期）"""
    try:
        from api.signals.northbound import get_northbound_sentiment
        result = get_northbound_sentiment(days=0, as_of=as_of)
        val = result.get("value")
        if val is not None:
            return float(round(float(val) * 0.1429, 1))  # 1/7
    except Exception:
        pass
    return None


def _score_volume(as_of=None) -> Optional[float]:
    """量能分 → 情绪子分（支持历史日期）"""
    try:
        from api.signals.volume import get_volume_score
        result = get_volume_score(days=0, as_of=as_of)
        val = result.get("value")
        if val is not None:
            return float(round(float(val) * 0.1429, 1))  # 1/7
    except Exception:
        pass
    return None


def _interpret(score: float) -> str:
    if score < 15:
        return "[算法输出] 极度悲观——估值便宜但市场恐慌"
    elif score < 30:
        return "[算法输出] 偏悲观——市场信心不足"
    elif score < 45:
        return "[算法输出] 中性偏冷——机会隐现但风险仍存"
    elif score < 55:
        return "[算法输出] 中性——市场不冷不热"
    elif score < 70:
        return "[算法输出] 中性偏暖——市场情绪向好"
    elif score < 85:
        return "[算法输出] 偏乐观——多数维度向好"
    else:
        return "[算法输出] 过度乐观——估值偏高，需警惕回撤"


def get_composite_score(days: int = 0) -> dict:
    if days > 0:
        return _composite_history(min(days, 365))
    return _composite_latest()


def _composite_latest() -> dict:
    pe_sub = _score_pe_from_api()
    erp_sub = _score_erp()
    macro_sub = _score_macro()
    breadth_sub = _score_breadth()
    margin_sub = _score_margin()
    northbound_sub = _score_northbound()
    volume_sub = _score_volume()

    components = {
        "pe_score": round(pe_sub, 1) if pe_sub is not None else None,
        "erp_score": round(erp_sub, 1) if erp_sub is not None else None,
        "macro_score": round(macro_sub, 1) if macro_sub is not None else None,
        "breadth_score": round(breadth_sub, 1) if breadth_sub is not None else None,
        "margin_score": round(margin_sub, 1) if margin_sub is not None else None,
        "northbound_score": round(northbound_sub, 1) if northbound_sub is not None else None,
        "volume_score": round(volume_sub, 1) if volume_sub is not None else None,
    }

    valid = [v for v in [pe_sub, erp_sub, macro_sub, breadth_sub,
                          margin_sub, northbound_sub, volume_sub] if v is not None]
    if not valid:
        return {
            "indicator": "composite", "value": None, "status": "no_data",
            "message": "所有子指标数据不可用", "components": components,
        }

    total = round(sum(valid), 1)
    return {
        "indicator": "composite", "value": total, "range": "0-100",
        "interpretation": _interpret(total), "components": components,
        "dimensions_valid": len(valid), "dimensions_total": 7,
        "as_of_date": date.today().isoformat(),
    }


def _score_pe_from_api() -> Optional[float]:
    """从 API 获取 PE 分位 → 反转情绪分"""
    try:
        from api.signals.pe import get_pe_signal
        result = get_pe_signal(days=0)
        pct = result.get("percentile")
        return _score_pe(pct)
    except Exception:
        return None


def _composite_history(days: int) -> dict:
    """
    真实历史回算：
    - PE: 从 PE 历史序列取每个采样点的分位
    - ERP: 用 PE 值 + 最新国债收益率计算（无历史国债数据，可接受近似）
    - Macro: 用 macro_score._compute(as_of=date) 逐点回算
    - Breadth: 用 get_sector_breadth(dt=date) 逐点回算
    """
    from api.signals.pe import _load_pe_data

    pe_data = _load_pe_data()
    if pe_data is None or len(pe_data) == 0:
        return {"indicator": "composite", "status": "no_data", "history": []}

    pe_data["date"] = pd.to_datetime(pe_data["date"])
    pe_data = pe_data.sort_values("date")

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    recent = pe_data[pe_data["date"] >= cutoff]
    if len(recent) == 0:
        return {"indicator": "composite", "status": "no_data", "history": []}

    # 周频采样（每周最后一个交易日）
    recent = recent.copy()
    recent["iso_year"] = recent["date"].dt.isocalendar().year.astype(int)
    recent["iso_week"] = recent["date"].dt.isocalendar().week.astype(int)
    weekly = recent.groupby(["iso_year", "iso_week"], sort=True).last().reset_index()
    weekly = weekly.sort_values("date")

    # 限制采样点数量避免太慢（约 30 点/半年）
    if len(weekly) > 40:
        step = max(1, len(weekly) // 35)
        weekly = weekly.iloc[::step]

    bond_yield = _get_bond_yield_latest()  # 国债利率变化慢，用最新值近似可接受

    history = []
    for _, row in weekly.iterrows():
        dt = row["date"]
        pe_val = float(row["pe"])

        # PE 分位（滚动 5 年）
        lookback = dt - pd.Timedelta(days=5*365)
        hist_window = pe_data[(pe_data["date"] >= lookback) & (pe_data["date"] <= dt)]
        if len(hist_window) >= 100:
            pct = round((hist_window["pe"] < pe_val).sum() / len(hist_window) * 100, 1)
        else:
            pct = None

        pe_sub = _score_pe(pct) if pct is not None else None
        erp = _compute_erp_from_pe(pe_val, bond_yield)
        erp_sub = _score_erp_value(erp) if erp is not None else None
        macro_sub = _score_macro(as_of=dt)
        breadth_sub = _score_breadth(as_of=dt)
        # v2.1: 新增 3 维历史回算
        margin_sub = _score_margin(as_of=dt)
        northbound_sub = _score_northbound(as_of=dt)
        volume_sub = _score_volume(as_of=dt)

        valid = [v for v in [pe_sub, erp_sub, macro_sub, breadth_sub,
                              margin_sub, northbound_sub, volume_sub] if v is not None]
        if len(valid) >= 4:  # 至少 4 维有效才写入（7维中）
            total = round(sum(valid), 1)
            history.append({
                "date": str(dt.date()),
                "score": total,
                "pe_percentile": pct,
                "dims": len(valid),
            })

    return {
        "indicator": "composite", "range": "0-100", "days": days,
        "samples": len(history),
        "as_of_date": date.today().isoformat(),
        "method_note": "PE逐日真实分位 + ERP(PE+最新国债) + 宏观逐日回算 + 行业宽度逐日回算",
        "history": history,
    }
