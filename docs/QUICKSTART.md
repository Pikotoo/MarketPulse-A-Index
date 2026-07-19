# 快速开始指南

> 5 分钟接入 MarketPulse API

---

## 1. 环境准备

- **Python 3.11+**（推荐）
- 或任意支持 HTTP 请求的语言

## 2. 安装

```bash
git clone <your-repo-url> marketpulse
cd marketpulse
pip install -r requirements.txt
```

## 3. 创建 API Key

```bash
python scripts/manage_keys.py create --email=your@email.com --tier=free
# 输出: ✅ 创建成功: mp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## 4. 启动服务

```bash
# Windows
双击 run.bat

# 或命令行
python api/app.py
```

服务运行在 `http://localhost:8898`

## 5. 第一个请求

```bash
# 健康检查（不需要 Key）
curl http://localhost:8898/api/v1/health

# PE 分位（需要 Key）
curl -H "X-API-Key: mp-xxxx" http://localhost:8898/api/v1/signal/pe-percentile
```

## 6. Python 调用

```python
import requests

API = "http://localhost:8898"
KEY = "mp-xxxx"

headers = {"X-API-Key": KEY}

# 综合情绪分 — 最全面的市场温度计
r = requests.get(f"{API}/api/v1/signal/composite", headers=headers)
data = r.json()["data"]
print(f"综合情绪: {data['value']}/100 — {data['interpretation']}")

# PE 估值计算器 — 输入 PE 查分位
r = requests.get(f"{API}/api/v1/tool/pe-calculator?pe=12.5", headers=headers)
data = r.json()["data"]
print(f"PE=12.5 处于 {data['percentile']}% 分位 — {data['zone']}")

# 宏观经济日历 — 未来 30 天数据发布日程
r = requests.get(f"{API}/api/v1/calendar/upcoming", headers=headers)
for evt in r.json()["data"]["events"]:
    print(f"{evt['date']}  {evt['name']} ({evt['country']})")

# 行业热力图 — 32 行业 60 日动量
r = requests.get(f"{API}/api/v1/signal/sector-heatmap", headers=headers)
for g in r.json()["data"]["groups"]:
    print(f"\n{g['name']}:")
    for s in g["sectors"]:
        bar = "🟢" if s["momentum_60d"] > 5 else "🔴" if s["momentum_60d"] < -5 else "⚪"
        print(f"  {bar} {s['name']}: {s['momentum_60d']:+.1f}%")
```

## 7. 仪表盘

浏览器打开 `http://localhost:8898/dashboard`，查看可视化仪表盘：
- 📊 市场全景（综合情绪仪表、信号灯、分维度卡片）
- 🏭 行业热力图（32 行业 treemap，色块=动量方向强度）
- 🔢 PE 估值计算器
- 📊 历史相似期对比表
- 📰 市场要闻
- 📅 宏观经济日历
- 💬 AI 数据助手

## 8. 设置每日自动更新

右键「以管理员身份运行」:
```
scripts\install_scheduled_task.bat
```

每天凌晨 6:00 自动执行：数据下载 → 信号预计算 → 数据库备份 → 新鲜度检查

---

## 下一步

- 📖 [完整 API 参考文档](api-reference.md)
- ❓ [常见问题 FAQ](FAQ.md)
- 📂 [Python 示例代码](examples/python/basic_usage.py)
