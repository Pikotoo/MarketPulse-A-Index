"""
MarketPulse-A-Index 配置
基于公开市场数据深度加工的量化指标计算服务

所有参数可通过 .env 文件或环境变量覆盖
"""

import os
from pathlib import Path

# ── 路径配置 ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
# 数据根目录：优先环境变量，其次 H:\数据大全（兼容旧部署），最后项目内 data_source/
def _resolve_data_root() -> Path:
    env_val = os.getenv("DATA_ROOT")
    if env_val:
        return Path(env_val)
    legacy = Path(r"H:\数据大全")
    if legacy.exists():
        return legacy
    return PROJECT_ROOT / "data_source"

DATA_ROOT = _resolve_data_root()

MACRO_DATA_DIR = DATA_ROOT / "宏观数据"
PE_CACHE_PATH = DATA_ROOT / "csi300_pe.parquet"

# MarketPulse-A-Index 数据目录（SQLite、日志等）
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "marketpulse.db"
LOGS_DIR = PROJECT_ROOT / "api" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── API 配置 ─────────────────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "8898"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_VERSION = "2.1.0"
HEALTH_ENDPOINT_URL = f"http://localhost:{API_PORT}/api/v1/health"
ALGORITHM_VERSION = "2026.07.17"
_DASHBOARD_KEY_FILE = DATA_DIR / ".dashboard_key"

def _load_or_create_dashboard_key() -> str:
    """加载持久化的 Dashboard Key，不存在则生成并保存"""
    env_val = os.getenv("DASHBOARD_KEY")
    if env_val:
        return env_val
    try:
        if _DASHBOARD_KEY_FILE.exists():
            saved = _DASHBOARD_KEY_FILE.read_text().strip()
            if saved:
                return saved
    except Exception:
        pass
    # 生成新 key 并持久化
    new_key = "mp-" + __import__("secrets").token_hex(16)
    try:
        _DASHBOARD_KEY_FILE.write_text(new_key)
    except Exception:
        pass
    return new_key

DASHBOARD_KEY = _load_or_create_dashboard_key()

# ── AI 配置 ─────────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# ── 限速配置（每秒最大请求数）─────────────────────────────
RATE_LIMITS = {
    "free": 1,
    "personal": 3,
    "pro": 10,
    "enterprise": 50,
}

# 每日调用量上限
DAILY_QUOTA = {
    "free": 50,
    "personal": 500,
    "pro": 5000,
    "enterprise": 100000,
}

# ── 信号计算参数 ─────────────────────────────────────────
PE_LOOKBACK_YEARS = 10          # PE 分位回溯年数（10年为机构标准，覆盖完整牛熊周期）
SECTOR_MA_WINDOW = 60          # 行业宽度 MA 窗口
MACRO_SCORE_WINDOW = 12        # 宏观评分回溯月数

# ── 免责声明（所有 API 响应强制注入）──────────────────────
DISCLAIMER = (
    "⚠️ 重要声明："
    "1. 本项目为技术研究框架，所有分数/标签/解读均为算法自动输出，不构成投资建议、交易推荐或市场预测。"
    "2. 作者非持牌投资顾问，项目代码仅供学习交流。据此操作风险自担。"
    "3. 数据基于公开渠道，不对准确性、完整性做担保。"
)
WARNING = "本响应由计算机算法自动生成，任何分数/解读均不代表投资建议。"
DATA_SOURCES = ["国家统计局", "中国人民银行", "沪深交易所公开数据", "中证指数公司"]
PROCESSING_NOTE = "本指标基于公开市场数据经自有算法加工生成，非原始行情数据分发"
