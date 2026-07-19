"""
响应格式中间件 — 统一 {meta, data} 双层结构

所有端点自动包装，确保免责声明和数据来源声明的强制注入。
"""

import time
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import jsonify

from config import API_VERSION, DISCLAIMER, WARNING, DATA_SOURCES, PROCESSING_NOTE, ALGORITHM_VERSION

# 东八区
TZ = timezone(timedelta(hours=8))


def _make_meta() -> dict:
    """生成统一 meta 块"""
    return {
        "version": API_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "data_sources": DATA_SOURCES,
        "processing_note": PROCESSING_NOTE,
        "disclaimer": DISCLAIMER,
        "warning": WARNING,
    }


def api_response(data: dict, status_code: int = 200):
    """标准成功响应"""
    meta = _make_meta()
    response = jsonify({"meta": meta, "data": data})
    response.status_code = status_code
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def api_error(error: str, code: str = "UNKNOWN", message: str = "",
              status_code: int = 500):
    """标准错误响应"""
    meta = _make_meta()
    response = jsonify({
        "meta": meta,
        "error": error,
        "code": code,
        "message": message
    })
    response.status_code = status_code
    return response


def signal_endpoint(f):
    """
    信号端点装饰器：自动包装 {meta, data} + 全局异常捕获
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            elapsed = time.time() - start_time

            if isinstance(result, dict):
                meta = _make_meta()
                meta["response_time_ms"] = round(elapsed * 1000, 1)
                return jsonify({"meta": meta, "data": result})
            return result

        except FileNotFoundError as e:
            return api_error("not_found", "DATA_NOT_FOUND",
                           f"所需数据文件不可用: {str(e)}", 404)

        except ValueError as e:
            return api_error("bad_data", "INVALID_DATA",
                           f"数据异常: {str(e)}", 500)

        except Exception as e:
            return api_error("internal_error", "INTERNAL_ERROR",
                           "服务器内部错误，请稍后重试", 500)

    return decorated
