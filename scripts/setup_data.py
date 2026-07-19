#!/usr/bin/env python3
"""
一键数据初始化脚本 — 为新用户下载所有需要的 .day 数据文件。

用法:
    python scripts/setup_data.py

数据下载到 data_source/ 目录（可通过 DATA_ROOT 环境变量覆盖）。
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DATA_ROOT = os.environ.get("DATA_ROOT", str(PROJECT_ROOT / "data_source"))


def download_macro_data():
    """下载宏观数据"""
    print("[1/2] 下载宏观数据...")
    try:
        from scripts.download_data import download_all
        download_all()
        print("  宏观数据下载完成")
    except ImportError:
        print("  [跳过] akshare 未安装或 download_data.py 不可用")
    except Exception as e:
        print(f"  [警告] 宏观数据下载失败: {e}")
        print("  服务仍可启动，部分信号将返回 no_data")


def download_sector_data():
    """下载行业数据"""
    print("[2/2] 检查行业数据...")
    sector_dir = Path(DEFAULT_DATA_ROOT) / "指数行情"
    if sector_dir.exists() and any(sector_dir.glob("**/*.day")):
        print("  行业数据已存在")
    else:
        print("  [提示] 行业数据需手动下载或通过 download_data.py 获取")
        print("  服务仍可启动，行业相关信号将返回 no_data")


def main():
    print("=" * 50)
    print("MarketPulse 数据初始化")
    print(f"数据目录: {DEFAULT_DATA_ROOT}")
    print("=" * 50)

    Path(DEFAULT_DATA_ROOT).mkdir(parents=True, exist_ok=True)

    download_macro_data()
    download_sector_data()

    print()
    print("初始化完成！运行以下命令启动服务:")
    print("  python api/app.py")
    print()
    print("然后打开浏览器访问: http://localhost:8898/dashboard")


if __name__ == "__main__":
    main()
