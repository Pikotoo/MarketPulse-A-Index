"""
宏观经济日历 — 重要经济数据发布日程

数据来源: 国家统计局官网日程、央行公开日程
以硬编码为主（日期相对固定），后续可接 API 动态更新

端点:
  GET /api/v1/calendar/upcoming  — 未来30天事件
  GET /api/v1/calendar/history   — 近3个月已发布事件?months=N
"""

import sys
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

from datetime import date, timedelta

# ── 国内固定日程 ─────────────────────────────────────────

CN_CALENDAR = [
    # 月度数据（每月固定日期左右）
    {"name": "CPI/PPI",         "freq": "monthly", "day_rule": (9, 11),  "desc": "居民消费价格指数 / 工业生产者出厂价格指数", "importance": "high"},
    {"name": "PMI",             "freq": "monthly", "day_rule": (30, 1),  "desc": "制造业/非制造业采购经理指数（月末或月初）", "importance": "high"},
    {"name": "M2/社融",         "freq": "monthly", "day_rule": (10, 15), "desc": "货币供应量与社会融资规模", "importance": "high"},
    {"name": "LPR报价",         "freq": "monthly", "day_rule": (20, 22), "desc": "贷款市场报价利率（每月20日）", "importance": "high"},
    {"name": "MLF操作",         "freq": "monthly", "day_rule": (15, 17), "desc": "中期借贷便利操作与利率", "importance": "high"},
    {"name": "规模以上工业增加值", "freq": "monthly", "day_rule": (14, 16), "desc": "工业产出增速", "importance": "medium"},
    {"name": "社会消费品零售总额", "freq": "monthly", "day_rule": (14, 16), "desc": "消费数据", "importance": "medium"},
    {"name": "固定资产投资",     "freq": "monthly", "day_rule": (14, 16), "desc": "基建/制造业/房地产投资", "importance": "medium"},
    {"name": "贸易进出口",       "freq": "monthly", "day_rule": (7, 14),  "desc": "海关总署进出口数据", "importance": "medium"},
    {"name": "外汇储备",         "freq": "monthly", "day_rule": (7, 8),   "desc": "央行外汇储备规模", "importance": "low"},
    {"name": "70城房价",         "freq": "monthly", "day_rule": (15, 18), "desc": "统计局70大中城市住宅价格", "importance": "medium"},

    # 季度数据
    {"name": "GDP",             "freq": "quarterly", "day_rule": (15, 20), "desc": "国内生产总值（1/4/7/10月发布）", "importance": "high"},
    {"name": "货币政策执行报告",  "freq": "quarterly", "day_rule": (10, 20), "desc": "央行季度货币政策报告", "importance": "high"},
]

# ── 海外日程 ──────────────────────────────────────────────

US_CALENDAR = [
    {"name": "美联储议息会议",    "freq": "8x/year", "days": [
        "2026-01-29", "2026-03-19", "2026-05-07", "2026-06-18",
        "2026-07-30", "2026-09-17", "2026-11-05", "2026-12-17",
    ], "desc": "FOMC利率决议，决定联邦基金利率", "importance": "high"},
    {"name": "美国CPI",          "freq": "monthly", "day_rule": (12, 15), "desc": "美国消费者价格指数", "importance": "high"},
    {"name": "美国非农就业",      "freq": "monthly", "day_rule": (1, 7),   "desc": "非农就业人数+失业率（每月第一个周五）", "importance": "high"},
    {"name": "杰克逊霍尔年会",     "freq": "yearly",  "days": ["2026-08-27"], "desc": "全球央行年会，政策信号重要窗口", "importance": "high"},
]


def _resolve_monthly(day_rule, year, month):
    """根据 day_rule(min, max) 推测当月发布日期"""
    from datetime import date
    d_min = date(year, month, min(day_rule[0], 28))
    d_max = date(year, month, min(day_rule[1], 28))
    # 返回范围的中间点
    mid = d_min + timedelta(days=(d_max - d_min).days // 2)
    return mid


def _next_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def get_upcoming(days=30):
    """获取未来N天的事件"""
    today = date.today()
    cutoff = today + timedelta(days=days)
    events = []

    # 国内月度事件
    cursor_year, cursor_month = today.year, today.month
    for _ in range(3):  # 看未来3个月
        for evt in CN_CALENDAR:
            if evt["freq"] == "monthly":
                d = _resolve_monthly(evt["day_rule"], cursor_year, cursor_month)
                if today <= d <= cutoff:
                    events.append({
                        "date": d.isoformat(), "event": evt["name"],
                        "country": "中国", "importance": evt["importance"],
                        "desc": evt.get("desc", ""),
                    })
            elif evt["freq"] == "quarterly":
                if cursor_month in [1, 4, 7, 10]:
                    d = _resolve_monthly(evt["day_rule"], cursor_year, cursor_month)
                    if today <= d <= cutoff:
                        events.append({
                            "date": d.isoformat(), "event": evt["name"],
                            "country": "中国", "importance": evt["importance"],
                            "desc": evt.get("desc", ""),
                        })
        cursor_year, cursor_month = _next_month(cursor_year, cursor_month)

    # 海外固定日期事件
    for evt in US_CALENDAR:
        if "days" in evt:
            for ds in evt["days"]:
                d = date.fromisoformat(ds)
                if today <= d <= cutoff:
                    events.append({
                        "date": d.isoformat(), "event": evt["name"],
                        "country": "美国", "importance": evt["importance"],
                        "desc": evt.get("desc", ""),
                    })
        elif evt["freq"] == "monthly":
            cursor_year, cursor_month = today.year, today.month
            for _ in range(3):
                d = _resolve_monthly(evt["day_rule"], cursor_year, cursor_month)
                if today <= d <= cutoff:
                    events.append({
                        "date": d.isoformat(), "event": evt["name"],
                        "country": "美国", "importance": evt["importance"],
                        "desc": evt.get("desc", ""),
                    })
                cursor_year, cursor_month = _next_month(cursor_year, cursor_month)

    events.sort(key=lambda x: x["date"])
    return {
        "indicator": "calendar_upcoming",
        "days": days,
        "count": len(events),
        "as_of_date": today.isoformat(),
        "events": events,
    }


def get_history(months=3):
    """获取近N个月已发布的事件"""
    today = date.today()
    start = today - timedelta(days=months * 31)
    events = []

    for m in range(months + 1):
        d = date(today.year, today.month, 1) - timedelta(days=m * 31)
        y, mo = d.year, d.month
        for evt in CN_CALENDAR:
            if evt["freq"] == "monthly":
                dt = _resolve_monthly(evt["day_rule"], y, mo)
                if start <= dt <= today:
                    events.append({
                        "date": dt.isoformat(), "event": evt["name"],
                        "country": "中国", "importance": evt["importance"],
                        "desc": evt.get("desc", ""),
                    })

    events.sort(key=lambda x: x["date"])
    return {
        "indicator": "calendar_history",
        "months": months,
        "count": len(events),
        "as_of_date": today.isoformat(),
        "events": events,
    }
