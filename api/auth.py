"""
API Key 认证系统 — 多用户、分级限速、用量统计

数据模型 (SQLite):
  api_keys: id, key_hash, email, tier, name, status, created_at
  usage_log: id, key_id, endpoint, timestamp
  daily_usage: id, key_id, date, request_count
"""

import sys
from pathlib import Path

# 确保 MarketPulse 的 config 优先被导入
_MP_ROOT = Path(__file__).parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

import hashlib
import secrets
import sqlite3
import time
from datetime import date
from typing import Optional
from functools import wraps
from flask import request, jsonify

from config import DB_PATH, RATE_LIMITS, DAILY_QUOTA

# ── DB 初始化 ────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT NOT NULL UNIQUE,
            email TEXT DEFAULT '',
            tier TEXT NOT NULL DEFAULT 'free',
            name TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            last_used_at TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (key_id) REFERENCES api_keys(id),
            UNIQUE(key_id, date)
        );

        CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_usage(date);
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
    """)
    conn.commit()
    conn.close()


def _hash_key(key: str) -> str:
    """SHA256 哈希"""
    return hashlib.sha256(key.encode()).hexdigest()


# ── Key 管理 ─────────────────────────────────────────────

def create_key(email: str = "", tier: str = "free", name: str = "") -> str:
    """创建新的 API Key，返回原始 Key"""
    raw_key = "mp-" + secrets.token_hex(16)
    key_hash = _hash_key(raw_key)

    conn = _get_db()
    conn.execute(
        "INSERT INTO api_keys (key_hash, email, tier, name) VALUES (?, ?, ?, ?)",
        (key_hash, email, tier, name)
    )
    conn.commit()
    conn.close()
    return raw_key


def list_keys() -> list:
    """列出所有 Key（不含原始值）"""
    conn = _get_db()
    rows = conn.execute("""
        SELECT id, key_hash, email, tier, name, status, created_at, last_used_at
        FROM api_keys ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_key(key_id: int):
    """删除 Key"""
    conn = _get_db()
    conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    conn.execute("DELETE FROM daily_usage WHERE key_id = ?", (key_id,))
    conn.commit()
    conn.close()


def disable_key(key_id: int):
    """禁用 Key"""
    conn = _get_db()
    conn.execute("UPDATE api_keys SET status = 'disabled' WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()


def enable_key(key_id: int):
    """启用 Key"""
    conn = _get_db()
    conn.execute("UPDATE api_keys SET status = 'active' WHERE id = ?", (key_id,))
    conn.commit()
    conn.close()


# ── 认证中间件 ───────────────────────────────────────────

class RateLimiter:
    """滑动窗口限速器（基于内存，定期清理过期条目）"""

    def __init__(self):
        self._windows: dict[str, list] = {}  # key_hash → [timestamps]
        self._last_cleanup = time.time()

    def check(self, key_hash: str, tier: str) -> tuple[bool, int]:
        """返回 (是否通过, 剩余可用次数)"""
        now = time.time()
        limit = RATE_LIMITS.get(tier, 1)
        window_size = 1.0  # 1秒窗口

        if key_hash not in self._windows:
            self._windows[key_hash] = []

        # 清理过期记录
        self._windows[key_hash] = [
            ts for ts in self._windows[key_hash]
            if now - ts < window_size
        ]

        count = len(self._windows[key_hash])

        if count >= limit:
            return False, 0

        self._windows[key_hash].append(now)
        remaining = limit - (count + 1)

        # 每 5 分钟清理一次无活跃记录的 key_hash（防止内存泄漏）
        if now - self._last_cleanup > 300:
            self._windows = {
                k: v for k, v in self._windows.items()
                if v and now - v[-1] < 3600  # 1小时内无请求则清除
            }
            self._last_cleanup = now

        return True, remaining


_rate_limiter = RateLimiter()


def _resolve_key(raw_key: str) -> Optional[dict]:
    """根据原始 Key 查找用户记录"""
    if not raw_key:
        return None
    key_hash = _hash_key(raw_key)
    conn = _get_db()
    row = conn.execute(
        "SELECT id, key_hash, tier, status FROM api_keys WHERE key_hash = ?",
        (key_hash,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _check_daily_quota(key_id: int, tier: str) -> tuple[bool, int]:
    """检查日配额，返回 (是否通过, 已用次数)

    使用 BEGIN IMMEDIATE 事务防止 TOCTOU 竞态条件。
    """
    today = date.today().isoformat()
    quota = DAILY_QUOTA.get(tier, 50)
    conn = _get_db()

    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT request_count FROM daily_usage WHERE key_id = ? AND date = ?",
            (key_id, today)
        ).fetchone()

        used = row["request_count"] if row else 0

        if used >= quota:
            conn.commit()
            return False, used

        conn.execute(
            "INSERT INTO daily_usage (key_id, date, request_count) VALUES (?, ?, 1) "
            "ON CONFLICT(key_id, date) DO UPDATE SET request_count = request_count + 1",
            (key_id, today)
        )
        conn.commit()
        return True, used + 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _update_last_used(key_id: int):
    """更新最后使用时间"""
    conn = _get_db()
    conn.execute(
        "UPDATE api_keys SET last_used_at = datetime('now', 'localtime') WHERE id = ?",
        (key_id,)
    )
    conn.commit()
    conn.close()


def require_api_key(f):
    """API Key 认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        raw_key = request.headers.get("X-API-Key", "")
        if not raw_key:
            return jsonify({
                "error": "unauthorized",
                "code": "MISSING_KEY",
                "message": "请在 X-API-Key 请求头中提供 API Key"
            }), 401

        user = _resolve_key(raw_key)
        if user is None:
            return jsonify({
                "error": "unauthorized",
                "code": "INVALID_KEY",
                "message": "无效的 API Key"
            }), 401

        if user["status"] == "disabled":
            return jsonify({
                "error": "forbidden",
                "code": "KEY_DISABLED",
                "message": "该 API Key 已被禁用"
            }), 403

        # 限速检查
        passed, _ = _rate_limiter.check(user["key_hash"], user["tier"])
        if not passed:
            return jsonify({
                "error": "rate_limited",
                "code": "TOO_MANY_REQUESTS",
                "message": f"请求频率超限（{user['tier']} 层级上限: {RATE_LIMITS.get(user['tier'], 1)}次/秒）"
            }), 429

        # 日配额检查
        passed, used = _check_daily_quota(user["id"], user["tier"])
        if not passed:
            return jsonify({
                "error": "quota_exceeded",
                "code": "DAILY_QUOTA_EXCEEDED",
                "message": f"今日调用次数已用完（{user['tier']} 层级上限: {DAILY_QUOTA.get(user['tier'], 50)}次/天）"
            }), 429

        # 更新使用时间
        _update_last_used(user["id"])

        # 注入用户信息
        request._marketpulse_user = user
        return f(*args, **kwargs)

    return decorated
