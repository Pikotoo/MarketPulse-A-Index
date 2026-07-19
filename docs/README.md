# MarketPulse v2.1 — A股市场情绪仪表盘

> 🌡️ 21 个量化信号指标，一个 API 全搞定。
>
> **卖算法不卖数据、卖指标不卖行情、做加工者不做搬运工**

---

## 这是什么？

MarketPulse 是一个轻量级 RESTful API，提供 **A股市场情绪、宽度、估值、流动性等衍生指标**。

与传统数据 API（TuShare、Wind）不同，MarketPulse **不提供原始行情数据**，而是输出加工后的分析指标：

```
❌ "000001 收盘价 12.50"              ← 传统数据 API
✅ "综合情绪 56.3/100，7维合成，中性"   ← MarketPulse
```

---

## ⚡ 快速开始

```bash
git clone <repo-url> && cd marketpulse
pip install -r requirements.txt
python scripts/manage_keys.py create --email=me@example.com --tier=free
python api/app.py
```

```bash
curl -H "X-API-Key: mp-xxxx" http://localhost:8898/api/v1/signal/composite
```

📖 [完整快速开始 →](QUICKSTART.md)

---

## 📊 21 个信号端点

| 分类 | 数量 | 端点示例 |
|------|:---:|------|
| 估值 | 2 | PE分位、ERP |
| 宏观 | 1 | 宏观9维评分 |
| 市场状态 | 3 | 综合情绪、恐慌指数、市场状态判定 |
| 行业 | 6 | 行业宽度、动量、热力图、拥挤度、风格轮动、防御比 |
| 资金面 | 6 | 融资融券、北向资金、量能、流动性、资金情绪、解禁压力 |
| 宽度 | 3 | 涨跌比、新高新低、跨资产对比 |

➕ 工具: PE计算器、相似期对比
➕ 资讯: 市场要闻、宏观日历
➕ AI: DeepSeek 数据助手

📖 [完整 API 文档 →](api-reference.md)

---

## 📦 项目亮点

- ⚡ **预计算缓存** — 每日凌晨自动计算，API 毫秒级响应
- 📊 **可视化仪表盘** — ECharts 交互式图表 + 行业热力图 + AI 对话
- 🔐 **四层限速** — free/personal/pro/enterprise
- 📅 **宏观经济日历** — 自动生成发布日程
- 🛡️ **合规优先** — 全端点强制注入免责声明

---

## 📖 文档导航

| 文档 | 说明 |
|------|------|
| [快速开始](QUICKSTART.md) | 5 分钟接入指南 |
| [API 参考](api-reference.md) | 全部 25 个端点详细文档 |
| [常见问题](FAQ.md) | FAQ |
| [Python 示例](examples/python/basic_usage.py) | Python 调用示例 |
| [curl 示例](examples/curl/examples.sh) | curl 一键测试 |

---

## ⚠️ 声明

- 本服务提供**量化指标计算**，非证券投资咨询
- 所有指标**不含买卖建议**，仅供研究参考
- 数据基于公开市场信息经自有算法加工，不保证准确性
- 指标设计方与数据提供方**不承担投资损失**

---

## 📬 申请试用

提交 [Issue 申请 API Key](.github/ISSUE_TEMPLATE/request_key.md)（免费版 50 次/天）。
