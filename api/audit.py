"""
审计日志 — 记录所有 /api/v1/ 请求到 SQLite

数据保留 6 个月，自动清理过期记录。
Key 存储为 SHA256 哈希，不存明文。
"""

import hashlib
import sqlite3
import time
from datetime import date, datetime, timedelta
from functools import wraps
from flask import request, g

from config import DB_PATH

# ── DB 初始化 ────────────────────────────────────────────

_AUDIT_RETENTION_DAYS = 180


def init_audit_db():
    """初始化审计日志表（在 auth.init_db 之后调用）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            api_key_hash TEXT DEFAULT '',
            endpoint TEXT NOT NULL,
            method TEXT DEFAULT 'GET',
            params TEXT DEFAULT '',
            status_code INTEGER DEFAULT 200,
            response_time_ms REAL DEFAULT 0,
            ip_address TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_logs(timestamp);

        CREATE INDEX IF NOT EXISTS idx_audit_endpoint
            ON audit_logs(endpoint);
    """)
    conn.commit()
    conn.close()


def _hash_key(raw_key: str) -> str:
    """Key → SHA256 哈希"""
    if not raw_key:
        return ""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _log_request(endpoint: str, status_code: int,
                 response_time_ms: float, params: str = ""):
    """写入一条审计日志（非阻塞）"""
    try:
        raw_key = request.headers.get("X-API-Key", "")
        ip = request.remote_addr or ""

        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            """INSERT INTO audit_logs
               (timestamp, api_key_hash, endpoint, method, params,
                status_code, response_time_ms, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                _hash_key(raw_key),
                endpoint,
                request.method,
                params[:500],  # 截断过长参数
                status_code,
                round(response_time_ms, 1),
                ip,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        # 审计日志写入失败不应影响 API 响应
        pass


def audit_trail(f):
    """
    审计装饰器：包装端点函数，记录请求和响应信息

    使用方式:
        @app.route("/api/v1/signal/xxx")
        @audit_trail
        def handler(): ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        start = time.time()

        # 构建参数字符串（用于审计）
        try:
            params = str(dict(request.args))
        except Exception:
            params = ""

        try:
            result = f(*args, **kwargs)
            elapsed = time.time() - start
            status_code = getattr(result, 'status_code', 200)
            _log_request(request.path, status_code, elapsed * 1000, params)
            return result
        except Exception:
            elapsed = time.time() - start
            _log_request(request.path, 500, elapsed * 1000, params)
            raise

    return decorated


def cleanup_old_logs():
    """清理超过保留期限的审计日志"""
    cutoff = (datetime.now() - timedelta(days=_AUDIT_RETENTION_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    try:
        conn = sqlite3.connect(str(DB_PATH))
        deleted = conn.execute(
            "DELETE FROM audit_logs WHERE timestamp < ?", (cutoff,)
        ).rowcount
        conn.commit()
        conn.close()
        return deleted
    except Exception:
        return 0
