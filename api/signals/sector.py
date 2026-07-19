"""
行业宽度信号 — 申万32行业站上MA60的比例

衡量全市场行业健康度，宽度越高表示越多行业处于上升趋势。

数据来源: 申万行业指数公开日线数据（.day格式）
加工深度: 原始行业日线 → MA60计算 → 行业站上/跌破判定 → 宽度聚合 → 排名输出
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

from api.day_reader import read_macro_series, list_macro_codes

# ── 申万行业编码映射 ─────────────────────────────────────
SECTOR_NAMES = {
    '990001': '农林牧渔', '990002': '采掘', '990003': '化工',
    '990004': '钢铁', '990005': '有色金属', '990006': '电子',
    '990007': '家用电器', '990008': '食品饮料', '990009': '纺织服装',
    '990010': '轻工制造', '990011': '医药生物', '990012': '公用事业',
    '990013': '交通运输', '990014': '房地产', '990015': '商业贸易',
    '990016': '休闲服务', '990017': '综合', '990018': '建筑材料',
    '990019': '建筑装饰', '990020': '电气设备', '990021': '国防军工',
    '990022': '计算机', '990023': '传媒', '990024': '通信',
    '990025': '银行', '990026': '非银金融', '990027': '汽车',
    '990028': '机械设备', '990029': '采掘服务', '990030': '轻工',
    '990032': '电子设备', '990033': '信息技术',
}

DEFENSIVE = {'990008', '990011', '990012', '990025', '990013'}
OFFENSIVE = {'990006', '990022', '990023', '990024', '990026', '990005', '990020'}

_cache = {}


def get_sector_codes() -> list:
    """获取所有申万行业代码（共享工具函数）"""
    all_codes = list_macro_codes()
    return [c for c in all_codes if c.startswith('9900') and len(c) == 6 and c[4:].isdigit()]


def _load_sector(code: str):
    if code in _cache:
        return _cache[code]
    try:
        df = read_macro_series(code)
        _cache[code] = df
        return df
    except FileNotFoundError:
        return None


def _above_ma(df: pd.DataFrame, window: int = 60,
              as_of: Optional[pd.Timestamp] = None) -> bool:
    """判断指数是否在MA上方"""
    if df is None or len(df) < window:
        return False
    if as_of is not None:
        nearby = df[df.index <= as_of]
    else:
        nearby = df
    if len(nearby) < window:
        return False
    ma = float(nearby['close'].iloc[-window:].mean())
    current = float(nearby['close'].iloc[-1])
    return current > ma


def _momentum(df: pd.DataFrame, days: int = 60,
              as_of: Optional[pd.Timestamp] = None) -> float:
    """N日动量"""
    if df is None or len(df) < days + 1:
        return 0.0
    if as_of is not None:
        nearby = df[df.index <= as_of]
    else:
        nearby = df
    if len(nearby) < days + 1:
        return 0.0
    current = float(nearby['close'].iloc[-1])
    past = float(nearby['close'].iloc[-(days + 1)])
    return (current - past) / past if past > 0 else 0.0


def _interpret_breadth(breadth: float) -> str:
    """解读行业宽度"""
    if breadth is None:
        return "未知"
    if breadth < 0.15:
        return "极度恐慌——几乎所有行业在MA60下方"
    elif breadth < 0.30:
        return "弱势——少数行业维持趋势"
    elif breadth < 0.50:
        return "分化——半数行业在趋势线上"
    elif breadth < 0.70:
        return "健康——多数行业处于上升趋势"
    elif breadth < 0.85:
        return "强势——乐观情绪蔓延"
    else:
        return "过热——几乎所有行业超买"


def _breadth_snapshot(target_date: pd.Timestamp) -> dict:
    """单日行业宽度快照（精简版，只用 core 计算）"""
    sector_codes = get_sector_codes()

    above_count = 0
    total = 0
    for code in sector_codes:
        df = _load_sector(code)
        if df is not None and _above_ma(df, 60, target_date):
            above_count += 1
        total += 1

    if total == 0:
        return None

    return {
        "breadth": round(above_count / total, 3),
        "above_count": above_count,
        "total_sectors": total,
    }


def get_sector_breadth(dt: Optional[date] = None, days: int = 0) -> dict:
    """
    行业宽度信号

    Args:
        dt: 指定日期（默认今天）
        days: 0=返回最新快照, >0=返回过去N天的历史序列（周频）

    Returns:
        单值模式: sector_breadth, sector_count, above_count, top_5, bottom_5, ...
        历史模式: history[{date, breadth, above_count}, ...]
    """
    if dt is None:
        dt = date.today()

    target_date = pd.Timestamp(dt)

    # ── 历史模式 ──
    if days > 0:
        days = min(days, 365)
        # 按交易日采样（跳过周六日）
        anchors = []
        cursor = pd.Timestamp.now() - pd.Timedelta(days=days)
        end = pd.Timestamp.now()
        while cursor <= end:
            if cursor.dayofweek < 5:  # 周一~周五
                anchors.append(cursor)
            cursor += pd.Timedelta(days=1)

        # 降采样到 ~3 天/点（数据太多图表卡）
        step = max(1, len(anchors) // 40)
        anchors = anchors[::step]

        history = []
        for anchor in anchors:
            snap = _breadth_snapshot(anchor)
            if snap is not None:
                history.append({
                    "date": anchor.strftime("%Y-%m-%d"),
                    "breadth": round(snap["breadth"] * 100, 1),
                    "above_count": snap["above_count"],
                    "total_sectors": snap["total_sectors"],
                })

        return {
            "indicator": "sector_breadth",
            "range": "0-100",
            "days": days,
            "samples": len(history),
            "as_of_date": date.today().isoformat(),
            "history": history,
        }

    # ── 单值模式 ──
    all_codes = list_macro_codes()
    sector_codes = [c for c in all_codes if c.startswith('9900') and len(c) == 6 and c[4:].isdigit()]

    momentums = {}
    above_ma = {}

    for code in sector_codes:
        df = _load_sector(code)
        if df is not None:
            momentums[code] = _momentum(df, 60, target_date)
            above_ma[code] = _above_ma(df, 60, target_date)

    n_sectors = len(momentums)
    if n_sectors == 0:
        return {
            "indicator": "sector_breadth",
            "value": None,
            "status": "no_data",
            "message": "无行业数据",
        }

    above_count = sum(1 for v in above_ma.values() if v)
    breadth = above_count / n_sectors

    # 7 日前宽度（趋势判断）
    seven_days_ago = target_date - pd.Timedelta(days=7)
    above_ma_7d = {}
    for code in momentums:
        df = _load_sector(code)
        if df is not None:
            above_ma_7d[code] = _above_ma(df, 60, seven_days_ago)
    breadth_7d = sum(1 for v in above_ma_7d.values() if v) / max(n_sectors, 1)

    if breadth - breadth_7d > 0.1:
        breadth_trend = "widening"
    elif breadth_7d - breadth > 0.1:
        breadth_trend = "narrowing"
    else:
        breadth_trend = "stable"

    # Top/Bottom 5 按动量排序
    sorted_mom = sorted(momentums.items(), key=lambda x: x[1], reverse=True)
    top_5 = [{"code": c, "name": SECTOR_NAMES.get(c, c), "momentum_60d": round(m * 100, 2)}
             for c, m in sorted_mom[:5]]
    bottom_5 = [{"code": c, "name": SECTOR_NAMES.get(c, c), "momentum_60d": round(m * 100, 2)}
                for c, m in sorted_mom[-5:]]

    # 防御/进攻比
    def_mom = [momentums.get(c, 0) for c in DEFENSIVE if c in momentums]
    off_mom = [momentums.get(c, 0) for c in OFFENSIVE if c in momentums]
    def_avg = np.mean(def_mom) if def_mom else 0
    off_avg = np.mean(off_mom) if off_mom else 0

    if off_avg > 0:
        dv0_ratio = round((def_avg - off_avg) / abs(off_avg), 3)
    else:
        dv0_ratio = 0.0

    if off_avg > def_avg + 0.03:
        risk_mode = "risk_on"
    elif def_avg > off_avg + 0.03:
        risk_mode = "risk_off"
    else:
        risk_mode = "neutral"

    return {
        "indicator": "sector_breadth",
        "value": round(breadth, 3),
        "range": "0-1",
        "sector_count": n_sectors,
        "above_ma60_count": above_count,
        "breadth_trend": breadth_trend,
        "top_5_sectors": top_5,
        "bottom_5_sectors": bottom_5,
        "defensive_vs_offensive": dv0_ratio,
        "risk_appetite": risk_mode,
        "interpretation": _interpret_breadth(breadth),
        "as_of_date": target_date.strftime("%Y-%m-%d"),
    }


def get_sector_heatmap(dt: Optional[date] = None, **kwargs) -> dict:
    """返回全部 32 行业动量数据，供热力图使用"""
    if dt is None:
        dt = date.today()
    target_date = pd.Timestamp(dt)

    all_codes = list_macro_codes()
    sector_codes = [c for c in all_codes if c.startswith('9900') and len(c) == 6 and c[4:].isdigit()]

    sectors = []
    for code in sector_codes:
        df = _load_sector(code)
        if df is not None:
            mom = _momentum(df, 60, target_date)
            above = _above_ma(df, 60, target_date)
            sectors.append({
                "code": code,
                "name": SECTOR_NAMES.get(code, code),
                "momentum_60d": round(mom * 100, 2),
                "above_ma60": above,
                "is_defensive": code in DEFENSIVE,
                "is_offensive": code in OFFENSIVE,
            })

    # 按动量排序
    sectors.sort(key=lambda x: x["momentum_60d"], reverse=True)

    return {
        "indicator": "sector_heatmap",
        "sectors": sectors,
        "total": len(sectors),
        "as_of_date": target_date.strftime("%Y-%m-%d"),
    }
