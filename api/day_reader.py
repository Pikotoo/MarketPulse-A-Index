"""
.day 二进制文件读取器（从 ashare-trader 移植）

.day 格式 (32字节/条, 小端序):
  - 4B: 日期 (YYYYMMDD, uint32)
  - 4B: 开盘 (float32)
  - 4B: 最高 (float32)
  - 4B: 低 (float32)
  - 4B: 收盘 (float32)
  - 4B: 成交额 (float32)
  - 4B: 成交量 (uint32)
  - 4B: 保留
"""

import struct
from pathlib import Path
from datetime import date, datetime
from typing import Optional, Dict

import pandas as pd

from config import MACRO_DATA_DIR

# ── 宏观数据代码 → 文件路径缓存 ──────────────────────────
_MACRO_INDEX: Dict[str, Path] = {}


def _build_macro_index():
    """扫描宏观数据目录，建立 CODE → 文件路径 映射"""
    global _MACRO_INDEX
    if _MACRO_INDEX:
        return
    if not MACRO_DATA_DIR.exists():
        return
    for fpath in MACRO_DATA_DIR.glob("38#*.day"):
        name = fpath.stem  # e.g., "38#3_PMI", "38#5_M2"
        parts = name.split("_", 1)
        if len(parts) == 2:
            code = parts[1]
            _MACRO_INDEX[code.upper()] = fpath


# 允许读取的文件目录白名单
_ALLOWED_DIRS = [MACRO_DATA_DIR]

# 延迟导入以避免循环引用
def _get_allowed_dirs() -> list:
    try:
        from config import DATA_ROOT
        if DATA_ROOT not in _ALLOWED_DIRS:
            _ALLOWED_DIRS.append(DATA_ROOT)
    except Exception:
        pass
    return _ALLOWED_DIRS


def read_day_file(path: str | Path) -> pd.DataFrame:
    """读取单个 .day 文件，返回 DataFrame（date索引, close列等）

    安全约束：仅允许读取白名单目录内的文件，防止路径遍历攻击。
    """
    path = Path(path).resolve()

    # 路径白名单校验
    allowed = _get_allowed_dirs()
    if not any(str(path).startswith(str(d.resolve())) for d in allowed):
        raise PermissionError(f"禁止访问目录外的文件: {path}")
    if not path.exists():
        raise FileNotFoundError(f"未找到文件: {path}")

    with open(path, "rb") as fh:
        data = fh.read()

    n = len(data) // 32
    if n == 0:
        raise ValueError(f"文件为空: {path}")

    records = []
    for i in range(n):
        offset = i * 32
        chunk = data[offset:offset + 32]
        dt_int, open_v, high_v, low_v, close_v, amount, volume, _ = \
            struct.unpack("<IfffffII", chunk)

        if dt_int < 19900101 or dt_int > 21000000:
            continue

        try:
            dt = datetime.strptime(str(dt_int), "%Y%m%d")
        except ValueError:
            continue

        records.append({
            "date": dt,
            "open": round(open_v, 4),
            "high": round(high_v, 4),
            "low": round(low_v, 4),
            "close": round(close_v, 4),
            "amount": round(amount, 2),
            "volume": int(volume),
        })

    if not records:
        raise ValueError(f"无有效记录: {path}")

    df = pd.DataFrame(records)
    df = df.set_index("date").sort_index()
    return df


def read_macro_series(code: str) -> pd.DataFrame:
    """读取宏观数据序列"""
    _build_macro_index()

    code_upper = code.upper()
    if code_upper in _MACRO_INDEX:
        return read_day_file(_MACRO_INDEX[code_upper])

    # 尝试模糊匹配
    for key, fpath in _MACRO_INDEX.items():
        if key.startswith(code_upper) or code_upper.startswith(key):
            return read_day_file(fpath)

    raise FileNotFoundError(f"未找到宏观指标: {code}")


def list_macro_codes() -> list:
    """列出所有可用的宏观指标代码"""
    _build_macro_index()
    return sorted(_MACRO_INDEX.keys())


def get_macro_value(code: str, as_of: date = None) -> Optional[float]:
    """获取某个宏观指标的最新值"""
    try:
        df = read_macro_series(code)
        if as_of is not None:
            df = df[df.index <= pd.Timestamp(as_of)]
        if len(df) == 0:
            return None
        return float(df["close"].iloc[-1])
    except (FileNotFoundError, ValueError):
        return None
