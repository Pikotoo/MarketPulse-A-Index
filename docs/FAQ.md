# 常见问题 FAQ

---

## 服务相关

### 数据多久更新一次？
每日凌晨 6:00 自动更新（数据下载 → 信号预计算）。API 请求优先读取缓存，毫秒级返回。宏观经济数据月度发布（CPI/PMI/M2 等），市场数据每个交易日更新。

### 免费版额度用完了怎么办？
- 每天 50 次调用，建议配合前端缓存（仪表盘默认 2 分钟刷新一次，一天约 720 次请求，建议至少使用 personal 层级）
- 升级到 personal（500次/天）或 pro（5000次/天）
- 联系管理员申请临时提额

### 支持历史数据回溯吗？
支持。大部分信号端点接受 `?days=N` 参数返回历史序列：

```bash
curl -H "X-API-Key: mp-xxxx" \
  "http://localhost:8898/api/v1/signal/composite?days=365"
```

返回 `history` 数组，包含每日的综合情绪分。

---

## 指标相关

### 指标是怎么计算的？
所有指标基于公开市场数据经自有算法加工。每个信号模块独立计算，详见 [API 参考文档](api-reference.md) 中各端点的算法说明。

核心原则：
- **硬过滤 > 评分微调**：坏信号直接拒绝，不在评分里加减分
- **等权合成 > 主观加权**：多维度取有效维度的等权平均
- **分位 > 绝对值**：PE、ERP 等估值指标用历史分位而非绝对值

### 综合情绪分包含哪些维度？
7 个维度等权合成：PE 分位、ERP（股权风险溢价）、宏观评分（9 维）、行业宽度、融资融券情绪、北向资金情绪、量能活跃度。综合分 > 60 偏乐观，< 40 偏悲观。

### 宏观评分包含哪些指标？
9 个维度：M2 同比增速、PMI 制造业指数、CPI 同比、SHIBOR 隔夜利率、国债期限利差（10Y-2Y）、美元兑人民币汇率、PPI 同比、M1-M2 剪刀差、FDI 外商直接投资。

### PE 分位的"极度低估"是怎么定义的？
基于近 5 年沪深 300 PE 历史分布：
- 分位 < 20%：极度低估
- 20-35%：低估
- 35-65%：合理
- 65-80%：偏高
- \> 80%：高估

---

## 技术相关

### 为什么选择 SQLite 而不是 PostgreSQL/MySQL？
- 零配置，数据量小（< 100MB），单机部署
- 读多写少场景，SQLite 性能足够
- 备份简单（单文件 `.db` 复制即可）
- 未来如果用户量上来，迁移到 PostgreSQL 只需改 `config.py` 一行

### 支持 Docker 部署吗？
预计 v2.2 提供 Dockerfile。当前可在 Linux 服务器上用 `gunicorn` 部署，参考 `deploy/marketpulse.service` 中的 systemd 配置。

### 怎么切换数据源路径？
数据根目录默认 `H:\数据大全`，可通过环境变量覆盖：

```bash
# Windows
set DATA_ROOT=D:\my_data

# Linux
export DATA_ROOT=/data/market-data
```

或在项目根目录创建 `.env` 文件（参考 `.env.example`）。

---

## 安全与合规

### 免责声明是真的吗？指标能用来做投资吗？
**严肃声明**：本服务所有指标仅供研究参考，不构成投资建议。指标基于公开数据经算法加工，不对准确性、完整性做担保。任何基于指标做出的投资决策，风险自行承担。

### API Key 怎么保管？
- 不要提交到 Git（`.gitignore` 已排除 `data/` 目录）
- 不要在前端代码中硬编码
- 生产环境建议通过环境变量注入

### 数据源合规吗？
所有数据来自公开渠道：国家统计局、中国人民银行、沪深交易所公开数据、中证指数公司。本服务做的是**衍生指标计算**，不涉及原始行情数据分发，合规风险远低于传统数据 API。

---

## 其他

### 有 SDK 吗？
Python SDK 正在规划中（v2.2）。目前可直接用 `requests` 库调用，参考 [Python 示例](examples/python/basic_usage.py)。

### 能导出 CSV 吗？
CSV 导出功能规划中。目前可通过 `/api/v1/signal/<name>?days=N` 获取历史 JSON 后自行转换：

```python
import csv, requests
r = requests.get("http://localhost:8898/api/v1/signal/composite?days=365",
                 headers={"X-API-Key": "mp-xxxx"})
history = r.json()["data"]["history"]
with open("composite.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["date", "score"])
    w.writeheader()
    w.writerows(history)
```

### 怎么反馈问题或提需求？
提交 GitHub Issue，或直接联系管理员。
