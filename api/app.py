"""
MarketPulse — A股市场信号指标 API v2.1

基于公开市场数据深度加工的量化指标计算服务
卖算法不卖数据、卖指标不卖行情、做加工者不做搬运工

端点 (21 信号 + 5 工具/资讯 + AI 对话):

估值维度:
  GET /api/v1/signal/pe-percentile    — 全市场PE分位
  GET /api/v1/signal/erp              — 股权风险溢价（股债性价比）

宏观维度:
  GET /api/v1/signal/macro-score      — 宏观综合评分（M2/PMI/CPI/SHIBOR/利差/汇率/PPI/M1M2/FDI 九维）
  GET /api/v1/signal/panic-index      — 恐慌指数（波动率+跌幅+宽度收缩）

市场状态:
  GET /api/v1/signal/composite        — 综合情绪分（PE+ERP+宏观+宽度+融资+北向+量能 七维合成）
  GET /api/v1/signal/regime           — 市场状态判定（极寒/偏冷/中性/偏热/过热）

行业维度:
  GET /api/v1/signal/sector-breadth   — 行业宽度（32行业站上MA60比例）
  GET /api/v1/signal/sector-momentum  — 行业动量排名
  GET /api/v1/signal/sector-heatmap   — 行业热力图（60日动量+攻防分组）
  GET /api/v1/signal/sector-crowding  — 行业拥挤度评分
  GET /api/v1/signal/style-rotation   — 风格轮动（大盘/小盘相对强度）
  GET /api/v1/signal/defensive-ratio  — 防御/进攻比值

资金面:
  GET /api/v1/signal/margin-sentiment    — 融资融券情绪分
  GET /api/v1/signal/northbound-sentiment — 北向资金情绪分
  GET /api/v1/signal/volume-score        — 量能活跃度
  GET /api/v1/signal/liquidity-score     — 流动性评分（SHIBOR/R007）
  GET /api/v1/signal/fund-sentiment      — 资金情绪综合
  GET /api/v1/signal/lockup-pressure     — 限售解禁压力分

市场宽度:
  GET /api/v1/signal/advance-decline  — 涨跌家数比
  GET /api/v1/signal/new-high-low     — 新高新低比
  GET /api/v1/signal/cross-asset      — 跨资产对比（股/债/商品）

工具 & 资讯:
  GET  /api/v1/tool/pe-calculator?pe=12.5  — PE 估值计算器
  GET  /api/v1/tool/similar-period?n=5     — 历史相似期查找
  GET  /api/v1/calendar/upcoming           — 宏观经济日历·未来
  GET  /api/v1/calendar/history            — 宏观经济日历·历史
  GET  /api/v1/news/latest                 — 市场要闻
  POST /api/v1/ai/chat                     — AI 数据助手（DeepSeek）

系统端点:
  GET /api/v1/health                  — 服务健康 + 数据新鲜度
  GET /api/v1/endpoints               — 可用端点列表

所有信号端点支持 ?days=N 历史序列查询 (N 最大 365)
认证: X-API-Key 请求头
"""

import sys
from pathlib import Path

# MarketPulse 项目根
_MP_ROOT = Path(__file__).parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

from flask import Flask, jsonify, send_from_directory, request
from datetime import date, datetime, timedelta

from api.auth import require_api_key, init_db
from api.middleware import signal_endpoint, api_response, api_error
from api.audit import audit_trail, init_audit_db
from api.cache import init_cache_db
from config import API_PORT, API_HOST, API_VERSION, DISCLAIMER

# ── NumPy JSON 编码支持 ─────────────────────────────────

try:
    import numpy as np
    import json as _json

    class _NumpyEncoder(_json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, (np.ndarray,)):
                return obj.tolist()
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            return super().default(obj)

    app = Flask(__name__)
    app.json_encoder = _NumpyEncoder
except ImportError:
    app = Flask(__name__)
PROJECT_ROOT = Path(__file__).parent.parent

# 启动时初始化数据库
with app.app_context():
    init_db()
    init_audit_db()
    init_cache_db()


# ── 辅助函数 ─────────────────────────────────────────────

def _get_days(default: int = 0) -> int:
    """安全获取 ?days=N 参数"""
    days = request.args.get("days", default, type=int)
    return max(0, min(days, 365))


def _cached_signal(indicator: str, compute_fn, days: int = 0):
    """
    信号端点缓存包装：
    - days=0 → 优先读今日缓存，未命中则实时计算并回写
    - days>0 → 仍实时计算（历史查询变化多，缓存命中率低）
    """
    from api.cache import get_cached, set_cache

    if days == 0:
        cached = get_cached(indicator)
        if cached is not None:
            return cached

    # 实时计算
    result = compute_fn(days=days) if days > 0 else compute_fn()

    # 回写今日缓存（仅单值）
    if days == 0:
        set_cache(indicator, result)

    return result


# ── 前端页面 ─────────────────────────────────────────────

@app.route("/")
@app.route("/dashboard")
def dashboard():
    """仪表盘首页"""
    return send_from_directory(str(PROJECT_ROOT), "dashboard.html")


@app.route("/s/<path:filename>")
def static_files(filename):
    """静态文件（JS/CSS/图片）"""
    from flask import send_from_directory
    return send_from_directory(str(PROJECT_ROOT / "static"), filename)


# ── 系统端点（不需要 Key）─────────────────────────────────

@app.route("/api/v1/health")
def health():
    """服务健康检查 + 数据新鲜度"""
    from api.day_reader import read_macro_series, list_macro_codes

    freshness = {}

    # 检查宏观数据
    try:
        pmi = read_macro_series("PMI")
        freshness["macro_pmi"] = {
            "latest_date": str(pmi.index[-1].date()),
            "records": len(pmi),
            "status": "ok" if len(pmi) > 0 else "no_data",
        }
    except Exception:
        freshness["macro_pmi"] = {"status": "unavailable"}

    # 检查 M2
    try:
        m2 = read_macro_series("M2")
        freshness["macro_m2"] = {
            "latest_date": str(m2.index[-1].date()),
            "records": len(m2),
            "status": "ok" if len(m2) > 0 else "no_data",
        }
    except Exception:
        freshness["macro_m2"] = {"status": "unavailable"}

    # 检查 PE 数据
    try:
        from api.signals.pe import _load_pe_data
        pe_data = _load_pe_data()
        if pe_data is not None and len(pe_data) > 0:
            if "date" in pe_data.columns:
                latest_date = str(pe_data["date"].iloc[-1].date())
            else:
                latest_date = str(pe_data.index[-1].date())
            freshness["pe_data"] = {
                "latest_date": latest_date,
                "records": len(pe_data),
                "status": "ok",
            }
        else:
            freshness["pe_data"] = {"status": "no_data"}
    except Exception:
        freshness["pe_data"] = {"status": "unavailable"}

    # 检查行业数据
    try:
        all_codes = list_macro_codes()
        sector_codes = [c for c in all_codes if c.startswith('9900') and len(c) == 6]
        freshness["sector_data"] = {
            "sectors_available": len(sector_codes),
            "status": "ok" if len(sector_codes) >= 25 else "degraded",
        }
    except Exception:
        freshness["sector_data"] = {"status": "unavailable"}

    return api_response({
        "service": "MarketPulse",
        "version": API_VERSION,
        "status": "running",
        "uptime": "active",
        "data_freshness": freshness,
    })


@app.route("/api/v1/endpoints")
def endpoints():
    """列出所有可用端点"""
    return api_response({
        "description": "MarketPulse API — A股市场信号指标",
        "authentication": "X-API-Key 请求头",
        "history_support": "所有信号端点支持 ?days=N (N≤365) 返回历史序列",
        "endpoints": [
            {"method": "GET", "path": "/api/v1/health", "auth_required": False,
             "description": "服务健康检查 + 数据新鲜度"},
            {"method": "GET", "path": "/api/v1/endpoints", "auth_required": False,
             "description": "可用端点列表"},

            {"method": "GET", "path": "/api/v1/signal/pe-percentile", "auth_required": True,
             "params": "?days=N", "description": "全市场PE分位 (0-100)"},
            {"method": "GET", "path": "/api/v1/signal/erp", "auth_required": True,
             "params": "?days=N", "description": "股权风险溢价 (%)"},
            {"method": "GET", "path": "/api/v1/signal/macro-score", "auth_required": True,
             "params": "?days=N", "description": "宏观综合评分 (0-100)"},
            {"method": "GET", "path": "/api/v1/signal/panic-index", "auth_required": True,
             "params": "?days=N", "description": "恐慌指数 (0-100)"},
            {"method": "GET", "path": "/api/v1/signal/sector-breadth", "auth_required": True,
             "params": "?days=N", "description": "行业宽度 — 站上MA60比例"},
            {"method": "GET", "path": "/api/v1/signal/defensive-ratio", "auth_required": True,
             "description": "防御/进攻比"},
            {"method": "GET", "path": "/api/v1/signal/sector-momentum", "auth_required": True,
             "params": "?days=N", "description": "行业动量 — 32行业涨跌排名"},
            {"method": "GET", "path": "/api/v1/signal/advance-decline", "auth_required": True,
             "params": "?days=N", "description": "涨跌比 — 上涨vs下跌行业数"},
            {"method": "GET", "path": "/api/v1/signal/new-high-low", "auth_required": True,
             "params": "?days=N", "description": "新高新低 — 创60日新高/新低行业数"},
            {"method": "GET", "path": "/api/v1/signal/composite", "auth_required": True,
             "params": "?days=N", "description": "综合情绪分 (0-100)"},
        ],
        "disclaimer": DISCLAIMER,
    })


@app.route("/api/v1/dashboard-key")
def dashboard_key():
    """仪表盘获取临时 API Key（不暴露在 HTML 源码中）"""
    from config import DASHBOARD_KEY
    return jsonify({"key": DASHBOARD_KEY})


@app.route("/api/v1/ai/chat", methods=["POST"])
def ai_chat():
    """AI 对话 — 只解释数据含义，不荐股"""
    import os, json as _json, urllib.request

    # API Key: 优先环境变量 DEEPSEEK_API_KEY，其次 config.py 中的配置
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        try:
            from config import DEEPSEEK_API_KEY
            api_key = DEEPSEEK_API_KEY
        except ImportError:
            pass

    if not api_key:
        return jsonify({"answer": "未配置 DeepSeek API Key。请在系统环境变量中设置 DEEPSEEK_API_KEY，或在 config.py 中添加。"})

    try:
        import requests as _req
        data = request.get_json(force=True)
        question = data.get("question", "")
        ctx = data.get("context", {})
        system_prompt = (
            "你是MarketPulse数据助手。只解释数据含义，绝不给出投资建议。"
            f"当前数据: 综合情绪={ctx.get('composite','?')}/100, "
            f"PE分位={ctx.get('pePct','?')}%, "
            f"市场状态={ctx.get('regime','?')}。"
            "用简洁中文，2-3句话。"
        )

        resp = _req.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "MarketPulse/2.1"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                "max_tokens": 200, "temperature": 0.3
            },
            timeout=20
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
        return jsonify({"answer": answer})
    except Exception as e:
        err_msg = str(e)[:300]
        # 尝试提取 DeepSeek 错误详情
        if hasattr(e, 'response') and e.response is not None:
            try: err_msg = e.response.json().get("error", {}).get("message", err_msg)
            except: pass
        return jsonify({"answer": f"AI 服务异常: {err_msg}"})


# ── 信号端点 ────────────────────────────────────────────

@app.route("/api/v1/signal/pe-percentile")
@audit_trail
@require_api_key
@signal_endpoint
def signal_pe():
    """PE分位 — 估值温度计"""
    from api.signals.pe import get_pe_signal
    return _cached_signal("pe_percentile", lambda days=0: get_pe_signal(days=days), _get_days())


@app.route("/api/v1/signal/erp")
@audit_trail
@require_api_key
@signal_endpoint
def signal_erp():
    """股权风险溢价 — 股债性价比"""
    from api.signals.erp import get_erp_signal
    return _cached_signal("erp", lambda days=0: get_erp_signal(days=days), _get_days())


@app.route("/api/v1/signal/macro-score")
@audit_trail
@require_api_key
@signal_endpoint
def signal_macro():
    """宏观综合评分 — 6维度合成"""
    from api.signals.macro_score import get_macro_score
    return _cached_signal("macro_score", lambda days=0: get_macro_score(days=days), _get_days())


@app.route("/api/v1/signal/panic-index")
@audit_trail
@require_api_key
@signal_endpoint
def signal_panic():
    """恐慌指数 — 波动率+离散度+宽度"""
    from api.signals.panic import get_panic_index
    return _cached_signal("panic_index", lambda days=0: get_panic_index(days=days), _get_days())


@app.route("/api/v1/signal/sector-breadth")
@audit_trail
@require_api_key
@signal_endpoint
def signal_sector():
    """行业宽度 — 32行业MA60站上比例"""
    from api.signals.sector import get_sector_breadth
    return _cached_signal("sector_breadth", lambda days=0: get_sector_breadth(days=days), _get_days())


@app.route("/api/v1/signal/defensive-ratio")
@audit_trail
@require_api_key
@signal_endpoint
def signal_defensive():
    """防御/进攻比 — 市场风险偏好"""
    from api.signals.sector import get_sector_breadth
    result = get_sector_breadth(days=0)
    ratio = result.get("defensive_vs_offensive", 0)
    appetite = result.get("risk_appetite", "neutral")
    return {
        "indicator": "defensive_ratio",
        "value": ratio,
        "risk_appetite": appetite,
        "interpretation": (
            "资金涌向防御" if ratio > 0.05
            else ("资金追逐进攻" if ratio < -0.05 else "攻防均衡")
        ),
        "note": "正值越大，资金越保守；负值越大，资金越激进",
        "as_of_date": result.get("as_of_date"),
    }


@app.route("/api/v1/signal/composite")
@audit_trail
@require_api_key
@signal_endpoint
def signal_composite():
    """综合情绪分 — 4维度等权合成 0-100"""
    from api.signals.composite import get_composite_score
    return _cached_signal("composite", lambda days=0: get_composite_score(days=days), _get_days())


@app.route("/api/v1/signal/advance-decline")
@audit_trail
@require_api_key
@signal_endpoint
def signal_ad():
    """涨跌比 — 行业上涨/下跌家数比"""
    from api.signals.breadth import get_advance_decline
    return _cached_signal("advance_decline", lambda days=0: get_advance_decline(days=days), _get_days())


@app.route("/api/v1/signal/new-high-low")
@audit_trail
@require_api_key
@signal_endpoint
def signal_nhl():
    """新高新低 — 创60日新高 vs 新低的行业数"""
    from api.signals.breadth import get_new_high_low
    return _cached_signal("new_high_low", lambda days=0: get_new_high_low(days=days), _get_days())


@app.route("/api/v1/signal/sector-momentum")
@audit_trail
@require_api_key
@signal_endpoint
def signal_momentum():
    """行业动量 — 32行业60日涨跌幅排名"""
    from api.signals.breadth import get_sector_momentum
    return _cached_signal("sector_momentum", lambda days=0: get_sector_momentum(days=days), _get_days())


@app.route("/api/v1/signal/sector-heatmap")
@audit_trail
@require_api_key
@signal_endpoint
def signal_heatmap():
    """行业热力图 — 全部32行业动量+趋势数据"""
    from api.signals.sector import get_sector_heatmap
    return get_sector_heatmap()


# ── v2.1 新增信号端点 ──────────────────────────────────────

@app.route("/api/v1/signal/margin-sentiment")
@audit_trail
@require_api_key
@signal_endpoint
def signal_margin():
    """融资融券情绪分 — 杠杆资金情绪 0-100"""
    from api.signals.margin import get_margin_sentiment
    return _cached_signal("margin_sentiment", lambda days=0: get_margin_sentiment(days=days), _get_days())


@app.route("/api/v1/signal/volume-score")
@audit_trail
@require_api_key
@signal_endpoint
def signal_volume():
    """量能分 — 市场交投活跃度 0-100"""
    from api.signals.volume import get_volume_score
    return _cached_signal("volume_score", lambda days=0: get_volume_score(days=days), _get_days())


@app.route("/api/v1/signal/northbound-sentiment")
@audit_trail
@require_api_key
@signal_endpoint
def signal_northbound():
    """北向资金情绪分 — 外资流向情绪 0-100"""
    from api.signals.northbound import get_northbound_sentiment
    return _cached_signal("northbound_sentiment", lambda days=0: get_northbound_sentiment(days=days), _get_days())


@app.route("/api/v1/signal/lockup-pressure")
@audit_trail
@require_api_key
@signal_endpoint
def signal_lockup():
    """限售解禁压力分 — 筹码供给压力 0-100"""
    from api.signals.lockup import get_lockup_pressure
    return _cached_signal("lockup_pressure", lambda days=0: get_lockup_pressure(days=days), _get_days())


# ── v2.1 P2 信号端点 ──────────────────────────────────────

@app.route("/api/v1/signal/liquidity-score")
@audit_trail
@require_api_key
@signal_endpoint
def signal_liquidity():
    """流动性评分 — 资金面松紧 0-100"""
    from api.signals.liquidity import get_liquidity_score
    return _cached_signal("liquidity_score", lambda days=0: get_liquidity_score(days=days), _get_days())


@app.route("/api/v1/signal/sector-crowding")
@audit_trail
@require_api_key
@signal_endpoint
def signal_crowding():
    """行业拥挤度 — 资金集中度风险 0-100"""
    from api.signals.crowding import get_sector_crowding
    return _cached_signal("sector_crowding", lambda days=0: get_sector_crowding(days=days), _get_days())


@app.route("/api/v1/signal/style-rotation")
@audit_trail
@require_api_key
@signal_endpoint
def signal_style():
    """风格轮动 — 大盘/小盘 价值/成长"""
    from api.signals.style import get_style_rotation
    return get_style_rotation(days=_get_days())


@app.route("/api/v1/signal/fund-sentiment")
@audit_trail
@require_api_key
@signal_endpoint
def signal_fund():
    """资金情绪分 — 北向+融资+ETF 综合 0-100"""
    from api.signals.fund_sentiment import get_fund_sentiment
    return _cached_signal("fund_sentiment", lambda days=0: get_fund_sentiment(days=days), _get_days())


@app.route("/api/v1/signal/cross-asset")
@audit_trail
@require_api_key
@signal_endpoint
def signal_cross():
    """跨资产比较 — 股债商汇多资产 0-100"""
    from api.signals.cross_asset import get_cross_asset
    return _cached_signal("cross_asset", lambda days=0: get_cross_asset(days=days), _get_days())


@app.route("/api/v1/signal/regime")
@audit_trail
@require_api_key
@signal_endpoint
def signal_regime():
    """市场状态识别 — 恐慌/低迷/中性/乐观/亢奋"""
    from api.signals.regime import get_regime
    return get_regime(days=_get_days())


# ── v2.1 工具端点 ──────────────────────────────────────────

@app.route("/api/v1/tool/pe-calculator")
@audit_trail
@require_api_key
@signal_endpoint
def tool_pe_calculator():
    """估值计算器 — 输入PE值，返回当前分位和历史参照"""
    from api.signals.pe import _load_pe_data
    pe_input = request.args.get("pe", type=float)
    if pe_input is None or pe_input <= 0:
        return api_response({"error": "invalid_pe", "message": "请提供有效的PE值"}, status_code=400)

    pe_data = _load_pe_data()
    if pe_data is None or len(pe_data) == 0:
        return {"indicator": "pe_calculator", "status": "no_data"}

    import numpy as np
    current_pe = float(pe_data["pe"].iloc[-1])
    percentile = round((pe_data["pe"] < pe_input).sum() / len(pe_data) * 100, 1)

    # 历史 PE 分布参照点
    pe_values = pe_data["pe"].dropna()
    refs = {
        "min_5y": round(float(pe_values.min()), 2),
        "p10": round(float(np.percentile(pe_values, 10)), 2),
        "p25": round(float(np.percentile(pe_values, 25)), 2),
        "median": round(float(np.percentile(pe_values, 50)), 2),
        "p75": round(float(np.percentile(pe_values, 75)), 2),
        "p90": round(float(np.percentile(pe_values, 90)), 2),
        "max_5y": round(float(pe_values.max()), 2),
        "current": round(current_pe, 2),
    }

    if percentile < 20:
        zone = "极度低估"
    elif percentile < 35:
        zone = "低估"
    elif percentile < 65:
        zone = "合理"
    elif percentile < 80:
        zone = "偏高"
    else:
        zone = "高估"

    return {
        "indicator": "pe_calculator",
        "input_pe": pe_input,
        "percentile": percentile,
        "interpretation": f"PE={pe_input} 处于近5年 {percentile}% 分位，属于{zone}区间",
        "zone": zone,
        "reference_points": refs,
        "as_of_date": date.today().isoformat(),
    }


@app.route("/api/v1/tool/similar-period")
@audit_trail
@require_api_key
@signal_endpoint
def tool_similar_period():
    """相似期对比 — 找历史中与当前最接近的N个时间点，包含后续表现"""
    days = min(request.args.get("days", 365, type=int), 730)
    top_n = min(request.args.get("n", 5, type=int), 10)

    from api.signals.composite import _composite_history
    hist = _composite_history(days)

    if not hist.get("history"):
        return {"indicator": "similar_period", "status": "no_data", "history": []}

    records = hist["history"]
    if len(records) < 2:
        return {"indicator": "similar_period", "status": "insufficient_data"}

    # 构建日期 → (index, score) 查找表
    date_map = {}
    for i, r in enumerate(records):
        date_map[r["date"]] = (i, r.get("score"))

    current = records[-1]
    target_score = current.get("score", 50)

    # 找距离最近的 top_n
    candidates = []
    for r in records[:-1]:
        score = r.get("score")
        if score is None:
            continue
        dist = abs(score - target_score)
        candidates.append({"date": r["date"], "score": score, "distance": round(dist, 1)})

    candidates.sort(key=lambda x: x["distance"])
    top = candidates[:top_n]

    # 计算每个相似点之后 1/3/6 个月的变化
    from datetime import datetime as _dt
    horizons = {"1M": 30, "3M": 90, "6M": 180}

    for item in top:
        item_date = _dt.strptime(item["date"], "%Y-%m-%d")
        base_score = item["score"]
        item["forward"] = {}

        for label, offset_days in horizons.items():
            target_dt = item_date + timedelta(days=offset_days)
            target_str = target_dt.strftime("%Y-%m-%d")

            # 找 ≥target_str 的最近一个记录
            future = [r for r in records if r["date"] >= target_str]
            if future:
                fwd_score = future[0].get("score")
                if fwd_score is not None and base_score:
                    change = round(fwd_score - base_score, 1)
                    pct = round(change / base_score * 100, 1) if base_score != 0 else None
                    item["forward"][label] = {
                        "date": future[0]["date"],
                        "score": round(fwd_score, 1),
                        "change": change,
                        "change_pct": pct,
                    }

    return {
        "indicator": "similar_period",
        "target_score": target_score,
        "target_date": current.get("date"),
        "similar_periods": top,
        "note": "基于综合情绪分距离匹配，forward=该日期后N个月的指标变化。仅供研究参考，不暗示未来。",
        "as_of_date": date.today().isoformat(),
    }


# ── 新闻端点 ──────────────────────────────────────────────

@app.route("/api/v1/news/latest")
@audit_trail
@require_api_key
@signal_endpoint
def news_latest():
    """最新新闻 — 本地缓存"""
    from api.news import get_latest_news
    category = request.args.get("category")
    limit = min(request.args.get("limit", 15, type=int), 30)
    articles = get_latest_news(limit=limit, category=category)
    return {
        "indicator": "news",
        "count": len(articles),
        "articles": articles,
        "as_of_date": date.today().isoformat(),
    }


@app.route("/api/v1/news/refresh")
@audit_trail
@require_api_key
@signal_endpoint
def news_refresh():
    """刷新新闻 — 从RSS源抓取最新内容"""
    from api.news import refresh_from_rss, news_stats
    result = refresh_from_rss()
    result["stats"] = news_stats()
    return result


# ── 宏观日历端点 ──────────────────────────────────────────

@app.route("/api/v1/calendar/upcoming")
@audit_trail
@require_api_key
@signal_endpoint
def calendar_upcoming():
    """宏观经济日历 — 未来30天"""
    from api.signals.calendar import get_upcoming
    days = request.args.get("days", 30, type=int)
    return get_upcoming(days=min(days, 90))


@app.route("/api/v1/calendar/history")
@audit_trail
@require_api_key
@signal_endpoint
def calendar_history():
    """宏观经济日历 — 历史"""
    from api.signals.calendar import get_history
    months = request.args.get("months", 3, type=int)
    return get_history(months=min(months, 12))


# ── 全局错误处理 ────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return api_response(
        {"error": "endpoint_not_found", "message": "不存在的端点"},
        status_code=404
    )


@app.errorhandler(405)
def method_not_allowed(e):
    return api_response(
        {"error": "method_not_allowed", "message": "不支持的请求方法"},
        status_code=405
    )


@app.errorhandler(500)
def server_error(e):
    return api_response(
        {"error": "internal_error", "message": "服务器内部错误"},
        status_code=500
    )


# ── 启动 ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(f"  MarketPulse API v{API_VERSION}")
    print(f"  :{API_PORT}")
    print()
    print("  ( X-API-Key):")
    print("    GET /api/v1/signal/pe-percentile    — PE")
    print("    GET /api/v1/signal/erp              — ")
    print("    GET /api/v1/signal/macro-score      — ")
    print("    GET /api/v1/signal/panic-index      — ")
    print("    GET /api/v1/signal/sector-breadth   — ")
    print("    GET /api/v1/signal/defensive-ratio  — /")
    print("    GET /api/v1/signal/composite        — ")
    print()
    print("  ():")
    print("    GET /api/v1/health                  — ")
    print("    GET /api/v1/endpoints               — ")
    print()
    print(f"  Key: py -3.11 scripts/manage_keys.py create --email=you@example.com")
    print("=" * 60)
    app.run(host=API_HOST, port=API_PORT, debug=False)
