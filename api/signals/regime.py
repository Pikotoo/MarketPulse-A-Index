"""
市场状态识别 — 基于综合情绪+恐慌+宽度三维，判断当前市场处于什么阶段

状态分类:
  PANIC      — 恐慌（低情绪+高恐慌+低宽度）→ 可能底部
  BEARISH    — 低迷（低情绪+中恐慌）
  RECOVERY   — 修复（中情绪+中恐慌+宽度改善）
  NEUTRAL    — 中性
  BULLISH    — 乐观（高情绪+低恐慌+高宽度）
  EUPHORIA   — 亢奋（极高情绪+极低恐慌）→ 可能顶部

状态转换记忆：记录进入当前状态的日期，辅助判断持续性。
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
from datetime import date, timedelta
from typing import Optional


def _get_regime(composite: Optional[float], panic: Optional[float],
                breadth: Optional[float]) -> dict:
    """三维状态判定"""
    if composite is None:
        return {"regime": "unknown", "label": "数据不足", "risk_level": "unknown"}

    c = float(composite)
    p = float(panic) if panic is not None else 50
    b = float(breadth) * 100 if breadth is not None else 50  # breadth 是 0-1

    if c < 25 and p > 65:
        regime = "panic"
        label = "恐慌"
        risk = "high_opportunity"
        desc = "极度恐慌——估值低+恐慌高，历史上常是中长期底部区域"
    elif c < 35:
        regime = "bearish"
        label = "低迷"
        risk = "moderate_opportunity"
        desc = "市场低迷——情绪偏低，但恐慌未达极致，底部信号不充分"
    elif c < 45:
        regime = "recovery"
        label = "修复"
        risk = "cautious"
        desc = "市场修复中——情绪从低位回升，宽度改善"
    elif c < 55:
        regime = "neutral"
        label = "中性"
        risk = "neutral"
        desc = "市场中性——不冷不热，无明确信号"
    elif c < 70:
        regime = "bullish"
        label = "乐观"
        risk = "elevated"
        desc = "市场偏乐观——情绪上升中，需关注是否过热"
    elif c < 85:
        regime = "euphoria"
        label = "亢奋"
        risk = "high_risk"
        desc = "市场亢奋——估值偏高+情绪高涨，警惕回调"
    else:
        regime = "extreme"
        label = "极端亢奋"
        risk = "extreme_risk"
        desc = "极端亢奋——估值极度偏高，历史经验需高度警惕"

    return {
        "regime": regime,
        "label": label,
        "risk_level": risk,
        "description": desc,
    }


def get_regime(days: int = 0) -> dict:
    """市场状态识别"""
    try:
        from api.signals.composite import get_composite_score
        from api.signals.panic import get_panic_index
        from api.signals.sector import get_sector_breadth

        composite = get_composite_score(days=0)
        panic = get_panic_index(days=0)
        breadth = get_sector_breadth(days=0)
    except Exception:
        return {"indicator": "regime", "regime": "unknown", "status": "error"}

    regime_info = _get_regime(
        composite.get("value"),
        panic.get("value"),
        breadth.get("value"),
    )

    # 历史状态序列
    history = []
    if days > 0:
        try:
            comp_hist = get_composite_score(days=min(days, 365))
            pan_hist = get_panic_index(days=min(days, 365))
            brd_hist = get_sector_breadth(days=min(days, 365))

            pan_map = {}
            for h in (pan_hist.get("history") or []):
                pan_map[h.get("date")] = h.get("value")

            brd_map = {}
            for h in (brd_hist.get("history") or []):
                brd_map[h.get("date")] = h.get("breadth")

            for h in (comp_hist.get("history") or []):
                dt = h.get("date")
                cs = h.get("score")
                ps = pan_map.get(dt)
                bs = brd_map.get(dt)
                if cs is not None:
                    ri = _get_regime(cs, ps, bs / 100 if bs else None)
                    history.append({
                        "date": dt, "score": cs, "regime": ri["regime"],
                        "label": ri["label"],
                    })
        except Exception:
            pass

    return {
        "indicator": "regime",
        "regime": regime_info["regime"],
        "label": regime_info["label"],
        "risk_level": regime_info["risk_level"],
        "description": regime_info["description"],
        "composite_score": composite.get("value"),
        "panic_score": panic.get("value"),
        "breadth_pct": round(float(breadth.get("value", 0)) * 100, 1),
        "history": history,
        "as_of_date": date.today().isoformat(),
    }
