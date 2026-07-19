# A-Index 开发路线图

> A股市场情绪指标 API — 卖算法不卖数据  
> 当前版本: v2.1.0 | 最后更新: 2026-07-17

---

## ✅ v2.0 已完成

### 数据管线
- [x] 数据源切换至 H:\数据大全（唯一数据源）
- [x] PE/PMI/CPI/M2/SHIBOR/汇率 下载修复
- [x] 每日定时更新 + 新鲜度检查

### 前端 v2
- [x] Vue 3 暗色主题仪表盘（桌面+手机双端响应式）
- [x] 4个Tab: 首页/行业/深度/API
- [x] 首页12模块: 情绪分·PE·北向·融资·量能·涨跌比·解禁·宏观·日历·新闻·更新
- [x] AI 聊天嵌入（底部固定+DeepSeek上下文注入）
- [x] ECharts 综合情绪历史曲线
- [x] 行业热力图（32行业动量着色）

### 后端
- [x] AI对话端点 `/api/v1/ai/chat`
- [x] composite 历史真实逐日回算
- [x] Dashboard Key 动态获取
- [x] 数据源统一

### 基础设施
- [x] Flask API 框架 + 统一 {meta, data} 响应
- [x] API Key 认证（4 层级 + SHA256 哈希）
- [x] 分级限速（滑动窗口） + 日配额
- [x] 审计日志（全链路记录）
- [x] NumPy JSON 编码器
- [x] Key 管理 CLI (`scripts/manage_keys.py`)

### v2.0 信号端点（10 个）
| 维度 | 端点 |
|------|------|
| 估值 | `pe-percentile` `erp` |
| 宏观 | `macro-score` `panic-index` |
| 行业 | `sector-breadth` `defensive-ratio` `sector-momentum` |
| 宽度 | `advance-decline` `new-high-low` |
| 综合 | `composite` |

### 系统端点
- [x] `health` — 数据新鲜度检查
- [x] `endpoints` — 端点列表
- [x] `calendar/upcoming` — 宏观经济日历

### 性能 & 运维
- [x] 信号预计算缓存（SQLite）
- [x] 每日自动预计算脚本 `scripts/update_signals.py`
- [x] 行业宽度历史改为交易日采样
- [x] DB 每日备份 `scripts/backup_db.py`（保留 30 天）
- [x] 数据下载脚本 `scripts/download_data.py`
- [x] 每日任务 `scripts/daily_task.bat`

### 前端 v1
- [x] 扁平化仪表盘（浅色主题）
- [x] ECharts 趋势图（PE+情绪 / 宽度+宏观）
- [x] 全指标悬停解释（data-tip）
- [x] 宏观经济日历展示

---

## ✅ v2.1 已完成 (2026-07-17)

### P1 信号（4个）— 资金面核心
- [x] 融资融券情绪分 `margin-sentiment` — 杠杆资金情绪 0-100
- [x] 量能分 `volume-score` — 市场交投活跃度 0-100
- [x] 北向资金情绪分 `northbound-sentiment` — 外资流向情绪 0-100
- [x] 限售解禁压力分 `lockup-pressure` — 筹码供给压力 0-100

### P2 信号（6个）— 扩展维度
- [x] 流动性评分 `liquidity-score` — SHIBOR/R007 资金面松紧
- [x] 行业拥挤度 `sector-crowding` — 资金集中度风险
- [x] 风格轮动 `style-rotation` — 大盘/小盘/价值/成长
- [x] 资金情绪综合 `fund-sentiment` — 北向+融资+ETF 三合一
- [x] 跨资产比较 `cross-asset` — 股/债/商品/汇率联动
- [x] 市场状态识别 `regime` — 极寒/偏冷/中性/偏热/过热

### 核心升级
- [x] 宏观评分 6→9 维（+PPI/M1M2剪刀差/FDI）
- [x] 综合情绪 4→7 维（+融资/北向/量能）
- [x] 工具端点: PE计算器 `/api/v1/tool/pe-calculator` + 相似期对比 `/api/v1/tool/similar-period`
- [x] 预计算缓存 9→17 信号
- [x] sector.breadth 历史数据缩放 bugfix

### 工程化
- [x] pyproject.toml 支持 pip install
- [x] Docker + docker-compose 一键部署
- [x] GitHub Actions CI
- [x] 一键数据初始化脚本 `scripts/setup_data.py`
- [x] 免责声明强化 + API warning 字段
- [x] Dashboard 首次访问免责弹窗
- [x] RSS 新闻聚合端点 `/api/v1/news/latest`

---

## ⬜ v2.2 计划

### P1 — 数据质量 🔴
- [ ] 数据下载脚本：修复 akshare PE 接口
- [ ] 数据下载脚本：修复 SHIBOR 列映射
- [ ] M2/PMI/CPI 增量更新逻辑（当前全量覆盖）
- [ ] 数据新鲜度告警（超过 N 天未更新 → 飞书/微信通知）

### P1 — 前端完善
- [ ] 估值计算器接入真实 PE 历史数据（当前用静态参照点）
- [ ] 相似期对比表（历史相似情绪区间的后续走势）
- [ ] 行业 Tab 数据完善（32行业详情页）
- [ ] 新闻模块前端接入（已有 `/api/v1/news/latest` 端点）

### P2 — 内容 & 推广
- [ ] 每周市场情绪周报（自动生成 + 邮件推送）
- [ ] 抖音账号 + AI工具故事
- [ ] 每日分享卡片生成（情绪仪表盘截图 + 一句话解读）

### P2 — 资讯模块
- [ ] 官方 RSS 聚合（央行/统计局/证监会）
- [ ] 资讯分类展示（标题+链接，不存正文 — 合规）

### P2 — 数据产品
- [ ] CSV 历史数据导出（付费功能）
- [ ] Python SDK（`pip install aindex`）

### P3 — 商业化
- [ ] 阈值告警（PE分位/恐慌/宽度超阈值 → 推送）
- [ ] 用户注册页面
- [ ] 付费体系上线

### P3 — 扩展
- [ ] 美股市场指标（VIX/SP500 PE/美债）
- [ ] 行业轮动策略回测（基于 sector-momentum 信号）

---

## 📊 统计

| 维度 | 完成 | 规划 | 进度 |
|------|:--:|:--:|:--:|
| 信号端点 | 21 | 21 | ✅ 100% |
| 系统端点 | 7 | 7 | ✅ 100% |
| 工具端点 | 2 | 3 | 67% |
| 前端模块 | 12 | 16 | 75% |
| 数据质量 | 3 | 7 | 43% |
| 内容产品 | 1 | 4 | 25% |

### 端点全景（21 信号 + 2 工具 + 7 系统 = 30）

```
估值:  pe-percentile  erp
宏观:  macro-score  panic-index
行业:  sector-breadth  sector-momentum  sector-heatmap
       sector-crowding  style-rotation  defensive-ratio
资金:  margin-sentiment  northbound-sentiment  volume-score
       liquidity-score  fund-sentiment  lockup-pressure
宽度:  advance-decline  new-high-low
综合:  composite  regime  cross-asset
工具:  pe-calculator  similar-period
系统:  health  endpoints  dashboard-key  ai/chat
       calendar/upcoming  calendar/history  news/latest
```

---

*最后更新: 2026-07-17 · 21信号全部到位，进入数据质量和产品化阶段*
