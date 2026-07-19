"""
行业拥挤度评分 — 判断行业动量是否过度集中（拥挤=风险）

指标:
  1. Top5 行业动量集中度 — 前5行业动量占全部32行业总动量的比例
  2. 动量离散度 — 32行业动量的标准差（越小=越同质化=拥挤）
  3. 领涨行业持续性 — Top3 行业连续领涨天数

输出: 0-100 分，越高=越拥挤（需警惕回调）
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
from datetime import date
from typing import Optional

from api.signals.sector import SECTOR_NAMES, _load_sector, _momentum, get_sector_codes


from api.utils import norm as _norm


def _get_all_momentums(as_of: Optional[pd.Timestamp] = None) -> list:
    """获取所有行业的60日动量"""
    if as_of is None:
        as_of = pd.Timestamp.now()
    codes = get_sector_codes()
    moms = []
    for code in codes:
        df = _load_sector(code)
        if df is not None:
            mom = _momentum(df, 60, as_of)
            moms.append({"code": code, "name": SECTOR_NAMES.get(code, code), "momentum": mom})
    return sorted(moms, key=lambda x: x["momentum"], reverse=True)


def _score_concentration(moms: list) -> dict:
    """Top5 集中度 → 子分数 (0.40)"""
    if len(moms) < 10:
        return {"value": None, "sub_score": None}
    all_mom = [m["momentum"] for m in moms]
    total_mom = sum(abs(m) for m in all_mom)
    top5_mom = sum(abs(m["momentum"]) for m in moms[:5])
    if total_mom <= 0:
        return {"value": 0, "sub_score": 0.0}
    ratio = top5_mom / total_mom
    s = _norm(ratio, 0.25, 0.55)
    return {"value": round(ratio * 100, 1), "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.40, 4)}


def _score_dispersion(moms: list) -> dict:
    """动量离散度 → 子分数 (0.35)"""
    if len(moms) < 10:
        return {"value": None, "sub_score": None}
    vals = [m["momentum"] * 100 for m in moms]
    std = float(np.std(vals))
    # std < 5% → 高度同质化（拥挤），std > 15% → 分化明显（健康）
    s = 1.0 - _norm(std, 5.0, 18.0)  # 反转：离散度越小分越高
    return {"value": round(std, 2), "unit": "%", "score": round(s, 3), "sub_score": round(s * 0.35, 4)}


def _score_persistence(moms: list, as_of=None) -> dict:
    """领涨持续性（简化：Top3 动量 vs 一个月前的 Top3 动量变化）→ 子分数 (0.25)"""
    if len(moms) < 10:
        return {"value": None, "sub_score": None}
    now_top3 = set(m["code"] for m in moms[:3])

    # 一个月前
    now_date = pd.Timestamp(as_of) if as_of else pd.Timestamp.now()
    month_ago = now_date - pd.Timedelta(days=21)
    old_moms = _get_all_momentums(month_ago)
    old_top5 = set(m["code"] for m in old_moms[:5])

    overlap = len(now_top3 & old_top5)
    # overlap 高 → 领涨板块不变 → 拥挤度偏高
    s = overlap / 3.0
    return {"value": overlap, "unit": "个（Top3保持率）", "score": round(s, 3), "sub_score": round(s * 0.25, 4)}


def _interpret(score):
    if score < 25: return "[算法输出] 极度分散——无明显主线"
    elif score < 40: return "[算法输出] 分散——各板块轮动活跃"
    elif score < 55: return "[算法输出] 正常——有主线但不过热"
    elif score < 70: return "[算法输出] 偏拥挤——资金明显集中"
    elif score < 85: return "[算法输出] 拥挤——热门赛道交易拥挤"
    return "[算法输出] 极度拥挤——需警惕踩踏"


def _crowding_history(days: int) -> dict:
    """行业拥挤度历史序列（周频采样）"""
    days = min(days, 365)
    end = pd.Timestamp.now()
    cursor = end - pd.Timedelta(days=days)

    anchors = []
    while cursor <= end:
        if cursor.dayofweek < 5:
            anchors.append(cursor)
        cursor += pd.Timedelta(days=4)

    if len(anchors) > 50:
        step = max(1, len(anchors) // 40)
        anchors = anchors[::step]

    history = []
    for a in anchors:
        try:
            moms = _get_all_momentums(as_of=a)
            if not moms or len(moms) < 10:
                continue
            s1 = _score_concentration(moms)
            s2 = _score_dispersion(moms)
            s3 = _score_persistence(moms, as_of=a)
            valid = [s["sub_score"] for s in [s1, s2, s3] if s["sub_score"] is not None]
            if len(valid) >= 2:
                total = round(sum(valid) * 100, 1)
                history.append({"date": a.strftime("%Y-%m-%d"), "score": total})
        except Exception:
            continue

    return {
        "indicator": "sector_crowding", "range": "0-100", "days": days,
        "samples": len(history), "as_of_date": date.today().isoformat(),
        "history": history,
    }


def get_sector_crowding(days: int = 0) -> dict:
    """行业拥挤度 0-100"""
    if days > 0:
        return _crowding_history(days)

    moms = _get_all_momentums()
    s1 = _score_concentration(moms)
    s2 = _score_dispersion(moms)
    s3 = _score_persistence(moms)

    subs = {"concentration": s1, "dispersion": s2, "persistence": s3}
    valid = [s["sub_score"] for s in subs.values() if s["sub_score"] is not None]
    n = len(valid)
    if n == 0:
        return {"indicator": "sector_crowding", "value": None, "status": "no_data", "sub_scores": subs}

    total = round(sum(valid) * 100, 1)
    return {
        "indicator": "sector_crowding", "value": total, "range": "0-100",
        "interpretation": _interpret(total), "sub_scores": subs,
        "top_3_sectors": [{"code": m["code"], "name": m["name"], "momentum": round(m["momentum"] * 100, 2)}
                          for m in moms[:3]] if moms else [],
        "dimensions_valid": n, "dimensions_total": 3,
        "as_of_date": date.today().isoformat(),
    }
