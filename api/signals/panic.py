"""
恐慌指数 — 综合波动率、行业宽度、行业离散度的市场恐慌情绪指标

数据来源: 申万行业指数公开日线
加工深度: 行业日线 → 波动率/离散度/宽度 → 0-100恐慌分

方法论:
  - 行业波动率飙升 → 恐慌上升（不稳定）
  - 行业离散度扩大 → 恐慌上升（板块分化加剧）
  - 宽度暴跌 → 恐慌上升（多数行业下跌）
  - 三者共振时恐慌分最高
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

from api.day_reader import list_macro_codes, read_macro_series
from api.signals.sector import SECTOR_NAMES, _load_sector

# ── 参数 ─────────────────────────────────────────────────
VOL_LOOKBACK = 20        # 波动率计算窗口
DISP_LOOKBACK = 60       # 离散度计算窗口
TREND_LOOKBACK = 20      # 趋势变化窗口


def _sector_daily_returns(code: str, lookback: int = 60,
                          as_of: Optional[pd.Timestamp] = None) -> pd.Series:
    """计算单个行业的日收益率序列"""
    df = _load_sector(code)
    if df is None or len(df) < 3:
        return pd.Series(dtype=float)

    if as_of is not None:
        df = df[df.index <= as_of]

    df = df.sort_index()
    returns = df['close'].pct_change().dropna()
    return returns.iloc[-lookback:]


def _sector_volatility(code: str, window: int = VOL_LOOKBACK,
                       as_of: Optional[pd.Timestamp] = None) -> float:
    """年化波动率"""
    rets = _sector_daily_returns(code, window, as_of)
    if len(rets) < 5:
        return None
    return float(rets.std() * np.sqrt(252))


def _avg_sector_volatility(as_of: Optional[pd.Timestamp] = None) -> float:
    """所有行业平均波动率"""
    all_codes = list_macro_codes()
    sector_codes = [c for c in all_codes if c.startswith('9900') and len(c) == 6]

    vols = []
    for code in sector_codes:
        v = _sector_volatility(code, VOL_LOOKBACK, as_of)
        if v is not None and v > 0:
            vols.append(v)

    return float(np.mean(vols)) if vols else None


def _sector_dispersion(as_of: Optional[pd.Timestamp] = None) -> float:
    """行业离散度（各行业60日动量的标准差）"""
    all_codes = list_macro_codes()
    sector_codes = [c for c in all_codes if c.startswith('9900') and len(c) == 6]

    momentums = []
    for code in sector_codes:
        df = _load_sector(code)
        if df is not None and len(df) >= 61:
            if as_of is not None:
                nearby = df[df.index <= as_of]
            else:
                nearby = df
            if len(nearby) >= 61:
                current = float(nearby['close'].iloc[-1])
                past = float(nearby['close'].iloc[-61])
                mom = (current - past) / past if past > 0 else 0
                momentums.append(mom)

    return float(np.std(momentums)) if momentums else None


def _sector_breadth_raw(as_of: Optional[pd.Timestamp] = None) -> float:
    """简化版行业宽度（不依赖 sector.py 的完整函数）"""
    from api.signals.sector import get_sector_breadth
    if as_of is not None:
        result = get_sector_breadth(dt=as_of.date())
    else:
        result = get_sector_breadth()
    return result.get('value', 0.5)


def _panic_level(total: float) -> tuple:
    """恐慌指数 → (level, color, description)"""
    if total < 20:
        return "[算法输出] 平静", "green", "市场波澜不惊，波动低、行业同步上涨，结构稳定"
    elif total < 35:
        return "[算法输出] 警惕", "yellow", "局部波动上升，但整体风险可控"
    elif total < 50:
        return "[算法输出] 焦虑", "yellow", "板块分化明显，市场方向不确定"
    elif total < 70:
        return "[算法输出] 恐慌", "red", "波动飙升、宽度崩塌，市场处于防御模式"
    else:
        return "[算法输出] 极度恐慌", "red", "所有指标共振，恐慌情绪弥漫，通常对应市场底部区域"


def _panic_snapshot(as_of: pd.Timestamp) -> dict:
    """单日恐慌指数快照"""
    # 1. 波动率分
    avg_vol = _avg_sector_volatility(as_of)

    vol_hist = []
    for months_back in range(0, 24, 3):
        hist_date = as_of - pd.Timedelta(days=90 * (months_back // 3 + 1))
        hv = _avg_sector_volatility(hist_date)
        if hv is not None:
            vol_hist.append(hv)

    if avg_vol and vol_hist:
        vol_median = np.median(vol_hist)
        vol_std = np.std(vol_hist) if len(vol_hist) > 1 else 0.05
        vol_zscore = (avg_vol - vol_median) / vol_std if vol_std > 0 else 0
        vol_score = round(40 / (1 + np.exp(-vol_zscore)), 1)
    else:
        vol_score = 20.0

    # 2. 离散度分
    disp = _sector_dispersion(as_of)

    disp_hist = []
    for months_back in range(1, 25, 3):
        hist_date = as_of - pd.Timedelta(days=90 * months_back)
        hd = _sector_dispersion(hist_date)
        if hd is not None:
            disp_hist.append(hd)

    if disp and disp_hist:
        disp_median = np.median(disp_hist)
        disp_std = np.std(disp_hist) if len(disp_hist) > 1 else 0.03
        disp_zscore = (disp - disp_median) / disp_std if disp_std > 0 else 0
        disp_score = round(30 / (1 + np.exp(-disp_zscore)), 1)
    else:
        disp_score = 15.0

    # 3. 宽度分
    breadth = _sector_breadth_raw(as_of)
    breadth_score = round((1 - breadth) * 30, 1)

    # 4. 合成
    total = round(min(100.0, vol_score + disp_score + breadth_score), 1)
    level, color, desc = _panic_level(total)

    return {
        "indicator": "panic_index",
        "value": total,
        "range": "0-100",
        "level": level,
        "color": color,
        "interpretation": desc,
        "components": {
            "volatility_score": vol_score,
            "avg_sector_volatility": round(avg_vol * 100, 2) if avg_vol else None,
            "dispersion_score": disp_score,
            "sector_dispersion": round(disp * 100, 2) if disp else None,
            "breadth_score": breadth_score,
            "sector_breadth": round(breadth * 100, 1),
        },
        "as_of_date": as_of.strftime("%Y-%m-%d"),
    }


def get_panic_index(as_of: Optional[pd.Timestamp] = None,
                    days: int = 0) -> dict:
    """
    恐慌指数 — 0-100，越高越恐慌

    Args:
        as_of: 指定基准日期
        days: 0=返回最新值, >0=返回过去N天的历史序列（月频采样）

    计算逻辑:
      1. 波动率分 (0-40): 行业平均波动率 vs 历史范围 → 归一化
      2. 离散度分 (0-30): 行业动量标准差 → 归一化
      3. 宽度分 (0-30): 宽度越低 → 恐慌越高 → (1 - breadth) * 30

    阈值参考:
      0-20:  平静 — 波动低、行业普涨、结构稳定
      20-40: 警惕 — 局部波动开始上升
      40-60: 焦虑 — 板块明显分化
      60-80: 恐慌 — 波动飙升 + 宽度崩塌
      80-100: 极度恐慌 — 所有信号共振
    """
    if as_of is None:
        as_of = pd.Timestamp.now()

    # ── 历史模式 ──
    if days > 0:
        days = min(days, 365)
        # 用 M2 序列作为时间锚（月频）
        try:
            m2 = read_macro_series("M2")
        except Exception:
            m2 = None

        if m2 is not None and len(m2) >= 2:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            anchors = m2[m2.index >= cutoff].index.tolist()
        else:
            anchors = [pd.Timestamp.now() - pd.Timedelta(days=i * 30)
                       for i in range(days // 30, 0, -1)]

        history = []
        for anchor in anchors:
            try:
                snap = _panic_snapshot(anchor)
                # 精简返回
                history.append({
                    "date": anchor.strftime("%Y-%m-%d"),
                    "value": snap["value"],
                    "level": snap["level"],
                    "color": snap["color"],
                })
            except Exception:
                continue

        return {
            "indicator": "panic_index",
            "range": "0-100",
            "days": days,
            "samples": len(history),
            "as_of_date": date.today().isoformat(),
            "history": history,
        }

    # ── 单值模式 ──
    return _panic_snapshot(as_of)
