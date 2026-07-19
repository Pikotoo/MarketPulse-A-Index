# MarketPulse API 参考文档 v2.1

> 基础 URL: `http://localhost:8898`
> 认证方式: `X-API-Key` 请求头
> 所有响应统一为 `{meta, data}` 双层结构

---

## 统一响应格式

```json
{
  "meta": {
    "version": "2.1.0",
    "generated_at": "2026-07-17T06:00:00+08:00",
    "data_sources": ["国家统计局", "中国人民银行", "沪深交易所公开数据", "中证指数公司"],
    "processing_note": "本指标基于公开市场数据经自有算法加工生成，非原始行情数据分发",
    "disclaimer": "仅供研究参考，不构成投资建议。数据基于公开市场信息经自有算法加工，不对准确性、完整性做担保。据此投资风险自担。",
    "response_time_ms": 8.5
  },
  "data": {
    "indicator": "composite",
    "value": 56.3,
    "interpretation": "中性"
  }
}
```

### 错误响应

```json
{
  "meta": { ... },
  "error": "unauthorized",
  "code": "INVALID_KEY",
  "message": "无效的 API Key"
}
```

---

## 系统端点（无需认证）

### `GET /api/v1/health`

服务健康检查 + 数据新鲜度。

```bash
curl http://localhost:8898/api/v1/health
```

### `GET /api/v1/endpoints`

列出所有可用端点及说明。

---

## 🔑 认证方式

所有信号/工具/资讯端点需要在请求头中携带 API Key：

```bash
curl -H "X-API-Key: mp-xxxx" http://localhost:8898/api/v1/signal/composite
```

Python:

```python
import requests
r = requests.get("http://localhost:8898/api/v1/signal/composite",
                 headers={"X-API-Key": "mp-xxxx"})
```

### 用户分层

| 层级 | 每秒请求 | 每日配额 |
|------|:---:|:---:|
| free | 1 | 50 |
| personal | 3 | 500 |
| pro | 10 | 5,000 |
| enterprise | 50 | 100,000 |

---

## 📊 估值维度

### `GET /api/v1/signal/pe-percentile`

沪深300 PE 在近 5 年历史中的分位。

| 字段 | 类型 | 说明 |
|------|------|------|
| `value` | float | 当前 PE |
| `percentile` | float | 历史分位 (0-100)，越低越便宜 |
| `lookback_years` | int | 回溯窗口 |
| `interpretation` | string | 极度低估/低估/合理/偏高/高估 |

### `GET /api/v1/signal/erp`

股权风险溢价 = 1/PE - 10年国债收益率。正值越大，股票相对债券越有吸引力。

| 字段 | 类型 | 说明 |
|------|------|------|
| `value` | float | ERP 值 (%) |
| `earnings_yield` | float | 盈利收益率 (%) |
| `bond_yield_10y` | float | 10年期国债收益率 (%) |
| `percentile` | float | ERP 历史分位 |
| `interpretation` | string | 股债性价比判断 |

---

## 🏭 宏观维度

### `GET /api/v1/signal/macro-score`

9 维度宏观指标等权合成（0-100）。>50 偏暖，<50 偏冷。

**9 个子维度**: M2同比、PMI、CPI同比、SHIBOR隔夜、国债期限利差、人民币汇率、PPI、M1-M2剪刀差、FDI

| 字段 | 说明 |
|------|------|
| `value` | 综合评分 0-100 |
| `dimensions_valid` | 有效维度数 |
| `dimensions_total` | 总维度数 (9) |
| `sub_scores` | 各子维度得分详情 |

---

## 📈 市场状态

### `GET /api/v1/signal/composite` ⭐

**综合情绪分** — PE + ERP + 宏观 + 行业宽度 + 融资融券 + 北向资金 + 量能 七维合成。

| 字段 | 说明 |
|------|------|
| `value` | 综合评分 0-100 |
| `dimensions_valid` | 有效维度数 |
| `dimensions_total` | 总维度数 (7) |
| `components` | 各组件得分 {pe_score, erp_score, macro_score, breadth_score, margin_score, northbound_score, volume_score} |

### `GET /api/v1/signal/panic-index`

恐慌指数 — 波动率 + 跌幅 + 宽度收缩三维合成。

### `GET /api/v1/signal/regime`

市场状态判定（5 档）：极寒/偏冷/中性/偏热/过热。

---

## 🏗️ 行业维度

### `GET /api/v1/signal/sector-breadth`

申万 32 行业站上 MA60 的比例。

| 字段 | 说明 |
|------|------|
| `value` | 站上 MA60 比例 (0-1) |
| `top_5_sectors` | 动量最强 5 行业 |
| `bottom_5_sectors` | 动量最弱 5 行业 |
| `risk_appetite` | risk_on / risk_off / neutral |

### `GET /api/v1/signal/sector-momentum`

32 行业 60 日动量排名（含动量值 + MA60 状态）。

### `GET /api/v1/signal/sector-heatmap`

行业热力图数据 — 60 日动量 + 进攻/防御/其他分组，配合前端 treemap 使用。

### `GET /api/v1/signal/sector-crowding`

行业拥挤度评分 — 基于波动率 + 成交额的拥挤度指标。

### `GET /api/v1/signal/style-rotation`

风格轮动 — 大盘/小盘指数相对强度对比。

### `GET /api/v1/signal/defensive-ratio`

防御型 vs 进攻型行业比值，判断市场风险偏好。

---

## 💰 资金面

### `GET /api/v1/signal/margin-sentiment`

融资融券情绪分 — 融资余额 YoY + 融资融券比值趋势 + 融资余额趋势。

| 字段 | 说明 |
|------|------|
| `value` | 融资情绪分 0-100 |
| `rz_balance` | 当前融资余额 |
| `rz_yoy_change_pct` | 融资余额同比变化率 |
| `sub_scores` | 3 个子分数详情 |

### `GET /api/v1/signal/northbound-sentiment`

北向资金情绪分 — 月度净流向百分位 + 季度趋势 + 连续流入/流出月数。

| 字段 | 说明 |
|------|------|
| `value` | 北向情绪分 0-100 |
| `flow_latest_month` | 近月净流入（累计值） |
| `sub_scores` | 3 个子分数 {recent_flow, quarterly_trend, continuity} |

### `GET /api/v1/signal/volume-score`

量能活跃度 — 成交额偏离 MA20 程度 + 量价配合健康度。

### `GET /api/v1/signal/liquidity-score`

流动性评分 — SHIBOR / R007 等短期利率指标。

### `GET /api/v1/signal/fund-sentiment`

资金情绪综合 — 融资 + 北向 + 量能的加权合成。

### `GET /api/v1/signal/lockup-pressure`

限售解禁压力分 — 解禁市值偏离 + 趋势 + 历史比值。

---

## 📏 市场宽度

### `GET /api/v1/signal/advance-decline`

涨跌家数比 — 上涨 vs 下跌家数。

### `GET /api/v1/signal/new-high-low`

新高新低比 — 创 60 日新高 vs 新低股票比例。

### `GET /api/v1/signal/cross-asset`

跨资产对比 — 股票/债券/商品的相对强弱。

---

## 🛠️ 工具端点

### `GET /api/v1/tool/pe-calculator?pe=12.5`

PE 估值计算器。输入 PE 值，返回在历史中的分位、估值区间、参考点位。

| 参数 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `pe` | float | ✅ | 要评估的 PE 值 |

**响应字段**: `percentile`, `zone` (极度低估/低估/合理/偏高/高估), `reference_points` (min/P10/P25/median/P75/P90/max)

### `GET /api/v1/tool/similar-period?days=730&n=5`

历史相似期查找。找到与当前综合情绪分最接近的历史日期，并给出后续 1/3/6 个月表现。

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `days` | int | 365 | 搜索范围（天，max 730） |
| `n` | int | 5 | 返回条数（max 10） |

---

## 📅 日历端点

### `GET /api/v1/calendar/upcoming?days=30`

未来宏观经济数据发布日程。

**覆盖事件**: CPI/PPI、PMI、M2/社融、LPR、MLF、工业增加值、社零、固投、贸易、外汇储备、房价、GDP、货币政策报告、FOMC、US CPI、US 非农

### `GET /api/v1/calendar/history?months=3`

历史已发布的宏观数据日程。

---

## 📰 资讯端点

### `GET /api/v1/news/latest?limit=15`

最新市场要闻（缓存 + RSS 聚合）。

### `GET /api/v1/news/refresh`

手动触发 RSS 新闻刷新。

---

## 🤖 AI 端点

### `POST /api/v1/ai/chat`

AI 数据助手（基于 DeepSeek）。

```json
{
  "question": "当前市场情绪如何？",
  "context": {
    "composite": 56.3,
    "pePct": 48.9,
    "regime": "中性"
  }
}
```

---

## 错误码

| HTTP | 错误码 | 说明 |
|:---:|------|------|
| 401 | `MISSING_KEY` | 未提供 API Key |
| 401 | `INVALID_KEY` | API Key 无效 |
| 403 | `KEY_DISABLED` | API Key 已禁用 |
| 429 | `TOO_MANY_REQUESTS` | 请求频率超限 |
| 429 | `DAILY_QUOTA_EXCEEDED` | 今日调用次数已用完 |
| 404 | `DATA_NOT_FOUND` | 所需数据不可用 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 |

---

## 所有端点一览

| # | 端点 | 分类 |
|---|------|------|
| 1 | `/api/v1/signal/pe-percentile` | 估值 |
| 2 | `/api/v1/signal/erp` | 估值 |
| 3 | `/api/v1/signal/macro-score` | 宏观 |
| 4 | `/api/v1/signal/composite` | 市场状态 |
| 5 | `/api/v1/signal/panic-index` | 市场状态 |
| 6 | `/api/v1/signal/regime` | 市场状态 |
| 7 | `/api/v1/signal/sector-breadth` | 行业 |
| 8 | `/api/v1/signal/sector-momentum` | 行业 |
| 9 | `/api/v1/signal/sector-heatmap` | 行业 |
| 10 | `/api/v1/signal/sector-crowding` | 行业 |
| 11 | `/api/v1/signal/style-rotation` | 行业 |
| 12 | `/api/v1/signal/defensive-ratio` | 行业 |
| 13 | `/api/v1/signal/margin-sentiment` | 资金面 |
| 14 | `/api/v1/signal/northbound-sentiment` | 资金面 |
| 15 | `/api/v1/signal/volume-score` | 资金面 |
| 16 | `/api/v1/signal/liquidity-score` | 资金面 |
| 17 | `/api/v1/signal/fund-sentiment` | 资金面 |
| 18 | `/api/v1/signal/lockup-pressure` | 资金面 |
| 19 | `/api/v1/signal/advance-decline` | 宽度 |
| 20 | `/api/v1/signal/new-high-low` | 宽度 |
| 21 | `/api/v1/signal/cross-asset` | 宽度 |
| — | `/api/v1/tool/pe-calculator` | 工具 |
| — | `/api/v1/tool/similar-period` | 工具 |
| — | `/api/v1/calendar/upcoming` | 日历 |
| — | `/api/v1/calendar/history` | 日历 |
| — | `/api/v1/news/latest` | 资讯 |
| — | `/api/v1/ai/chat` | AI |

---

## 代码示例

- [Python 基础调用](examples/python/basic_usage.py)
- [curl 快速测试](examples/curl/examples.sh)
