# Changelog

## v2.1.0 (2026-07-17)

### 新增
- 融资融券情绪分 `margin-sentiment`
- 量能活跃度分 `volume-score`
- 北向资金情绪分 `northbound-sentiment`
- 限售解禁压力分 `lockup-pressure`
- 流动性评分 `liquidity-score`
- 行业拥挤度 `sector-crowding`
- 风格轮动 `style-rotation`
- 资金情绪综合 `fund-sentiment`
- 跨资产比较 `cross-asset`
- 市场状态识别 `regime`
- PE 估值计算器 `/api/v1/tool/pe-calculator`
- 历史相似期对比 `/api/v1/tool/similar-period`
- 宏观评分从 6 维扩展到 9 维
- 综合情绪从 4 维扩展到 7 维（+融资/北向/量能）
- AI 对话端点 `/api/v1/ai/chat`
- RSS 新闻聚合端点 `/api/v1/news/latest`

### 修复
- 综合情绪历史曲线 4 维→7 维全量回算
- 行业宽度历史数据缩放到 0-100
- ECharts connectNulls 线段断裂
- Dashboard 热力图改用 CSS Grid（不再依赖 ECharts treemap）

### 工程化
- pyproject.toml 支持 pip install
- Docker + docker-compose 一键部署
- GitHub Actions CI
- 一键数据初始化脚本
- 免责声明强化 + API warning 字段
- Dashboard 首次访问免责弹窗

## v2.0.0 (2026-07)

- 初始版本：10 个信号端点 + 5 个系统端点
- Flask API + SQLite 预计算缓存
- 四级限速体系 + API Key 认证
- Dashboard 单页应用（Vue 3 + ECharts）
- 宏观经济日历
