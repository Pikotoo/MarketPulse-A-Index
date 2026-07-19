"""
信号预计算缓存

每日凌晨批量计算所有指标并缓存到 SQLite。
API 请求优先读缓存，缓存未命中时实时计算并回写。
"""

import json
import sqlite3
from datetime import date, timedelta
from typing import Optional

from config import DB_PATH


def _json_default(obj):
    """JSON序列化：正确处理numpy数值类型"""
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.ndarray,)): return obj.tolist()
        if isinstance(obj, (np.bool_,)): return bool(obj)
    except ImportError:
        pass
    return str(obj)


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_cache_conn():
    """获取缓存数据库连接"""
    return _db()


def init_cache_db():
    """初始化缓存表"""
    conn = _db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signal_cache (
            indicator TEXT NOT NULL,
            calc_date TEXT NOT NULL,
            data_json TEXT NOT NULL,
            cached_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (indicator, calc_date)
        );
        CREATE INDEX IF NOT EXISTS idx_cache_indicator ON signal_cache(indicator);
        CREATE INDEX IF NOT EXISTS idx_cache_date ON signal_cache(calc_date);
    """)
    conn.commit()
    conn.close()


def get_cached(indicator: str, calc_date: Optional[str] = None) -> Optional[dict]:
    """读缓存"""
    if calc_date is None:
        calc_date = date.today().isoformat()
    conn = _db()
    row = conn.execute(
        "SELECT data_json FROM signal_cache WHERE indicator=? AND calc_date=?",
        (indicator, calc_date)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["data_json"])
    return None


def set_cache(indicator: str, data: dict, calc_date: Optional[str] = None):
    """写缓存 — 正确处理numpy数值类型"""
    if calc_date is None:
        calc_date = date.today().isoformat()
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO signal_cache (indicator,calc_date,data_json,cached_at) "
        "VALUES (?,?,?,datetime('now','localtime'))",
        (indicator, calc_date, json.dumps(data, ensure_ascii=False, default=_json_default))
    )
    conn.commit()
    conn.close()


def clean_old_cache(days: int = 365):
    """清理N天前的旧缓存，防止数据库膨胀"""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    conn = _db()
    conn.execute("DELETE FROM signal_cache WHERE calc_date < ?", (cutoff,))
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    return deleted


def is_fresh(indicator: str) -> bool:
    """今天是否已有缓存"""
    return get_cached(indicator) is not None


def cache_stats() -> dict:
    """缓存统计"""
    conn = _db()
    today = date.today().isoformat()
    r1 = conn.execute("SELECT COUNT(*) as cnt FROM signal_cache WHERE calc_date=?", (today,)).fetchone()
    r2 = conn.execute("SELECT COUNT(*) as cnt FROM signal_cache").fetchone()
    r3 = conn.execute("SELECT DISTINCT indicator FROM signal_cache WHERE calc_date=?", (today,)).fetchall()
    conn.close()
    return {
        "today_cached": r1["cnt"] if r1 else 0,
        "total_cached": r2["cnt"] if r2 else 0,
        "cached_indicators": [r["indicator"] for r in r3],
        "as_of": today,
    }
