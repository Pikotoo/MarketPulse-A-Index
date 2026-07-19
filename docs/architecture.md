# MarketPulse 架构

## 整体架构

```
数据源 (.day 文件)
    │
    └─→ day_reader.py (统一读取接口)
            │
            ├── 估值维度 ─────────────────────
            │   ├── pe.py          PE 历史分位
            │   └── erp.py         股权风险溢价
            │
            ├── 宏观维度 ─────────────────────
            │   └── macro_score.py  9维宏观评分
            │       (M2/PMI/CPI/SHIBOR/利差/汇率/PPI/M1M2/FDI)
            │
            ├── 行业维度 ─────────────────────
            │   ├── sector.py      行业宽度/动量/热力图
            │   └── crowding.py    行业拥挤度
            │
            ├── 资金维度 ─────────────────────
            │   ├── margin.py      融资融券情绪
            │   ├── northbound.py  北向资金情绪
            │   └── fund_sentiment.py 资金情绪综合
            │
            ├── 量价维度 ─────────────────────
            │   ├── volume.py      量能活跃度
            │   └── lockup.py      限售解禁压力
            │
            ├── 风险维度 ─────────────────────
            │   ├── panic.py       恐慌指数
            │   └── liquidity.py   流动性评分
            │
            ├── 综合维度 ─────────────────────
            │   ├── composite.py   7维综合情绪 (整合以上)
            │   ├── regime.py      市场状态识别
            │   ├── style.py       风格轮动
            │   └── cross_asset.py 跨资产比较
            │
            └── 输出层 ───────────────────────
                │
                ├── api/app.py         Flask 路由 (32 routes)
                ├── api/middleware.py   统一 {meta, data} 响应
                ├── api/auth.py        API Key 认证 + 四级限速
                ├── api/cache.py       SQLite 预计算缓存
                │
                ├──→ Dashboard (Vue 3 + ECharts, 暗色主题)
                ├──→ AI Chat (DeepSeek)
                └──→ 外部 API 调用 (curl/Python SDK)
```

## 数据管线

```
scripts/download_data.py    →  数据下载 (akshare)
scripts/update_signals.py   →  信号预计算 (SQLite)
scripts/update_news.py      →  RSS 新闻聚合
scripts/backup_db.py        →  每日数据库备份
scripts/daily_task.bat      →  日频调度编排
```

## 响应格式

所有 API 端点返回统一结构：

```json
{
  "meta": {
    "version": "2.1.0",
    "algorithm_version": "2026.07.17",
    "generated_at": "2026-07-17T...",
    "data_sources": ["国家统计局", "中国人民银行", ...],
    "disclaimer": "⚠️ 重要声明...",
    "warning": "本响应由计算机算法自动生成..."
  },
  "data": {
    "indicator": "composite",
    "value": 56.3,
    "range": "0-100",
    "interpretation": "[算法输出] 中性偏暖——市场情绪向好"
  }
}
```
