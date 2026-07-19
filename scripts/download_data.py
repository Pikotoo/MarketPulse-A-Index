"""
数据更新脚本 — 用 akshare 下载最新宏观/汇率数据，追加到 .day 文件

.day 格式 (32字节/条, 小端序):
  4B date(YYYYMMDD) + 4B open + 4B high + 4B low + 4B close + 4B amount + 4B volume + 4B reserved

用法:
  py -3.11 scripts/download_data.py           # 增量更新
  py -3.11 scripts/download_data.py --check   # 只查不下载
"""

import struct
import sys
from pathlib import Path
from datetime import date, datetime, timedelta

_MP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_MP_ROOT))

import pandas as pd
import numpy as np

from config import MACRO_DATA_DIR
from api.day_reader import read_macro_series, _build_macro_index


def _read_day_dates(path):
    """读取 .day 文件中所有日期"""
    dates = set()
    if not path.exists():
        return dates
    with open(path, "rb") as f:
        data = f.read()
    for i in range(0, len(data), 32):
        dt_int = struct.unpack("<I", data[i:i+4])[0]
        if 19900101 < dt_int < 21000000:
            dates.add(dt_int)
    return dates


def _write_day_record(fh, dt, open_v, high_v, low_v, close_v, amount=0, volume=0):
    """写入一条 .day 记录"""
    fh.write(struct.pack("<IfffffII",
        int(dt.strftime("%Y%m%d")),
        float(open_v), float(high_v), float(low_v), float(close_v),
        float(amount), int(volume), 0))


def _append_to_day(path, records):
    """追加记录到 .day 文件（去重）"""
    existing = _read_day_dates(path)
    added = 0
    with open(path, "ab") as f:
        for rec in records:
            dt_int = int(rec["date"].strftime("%Y%m%d"))
            if dt_int not in existing:
                _write_day_record(f, rec["date"],
                    rec.get("open", rec["close"]),
                    rec.get("high", rec["close"]),
                    rec.get("low", rec["close"]),
                    rec["close"])
                existing.add(dt_int)
                added += 1
    return added


# ── 各数据源下载函数 ─────────────────────────────────────

def _download_rmb():
    """下载美元兑人民币中间价"""
    try:
        import akshare as ak
        df = ak.currency_boc_safe()  # SAFE 人民币汇率中间价
        if df is None or len(df) == 0:
            return None
        print(f"  RMB: got {len(df)} rows, latest {df['日期'].iloc[-1]} = {df['美元'].iloc[-1]}")
        return df
    except Exception as e:
        print(f"  RMB: failed - {str(e)[:60]}")
        return None


def _download_shibor():
    """下载 SHIBOR 隔夜"""
    try:
        import akshare as ak
        df = ak.macro_china_shibor_all()
        print("  SHIBOR: got", len(df) if df is not None else 0, "rows")
        return df
    except Exception as e:
        print("  SHIBOR: failed -", str(e)[:60])
        return None


def _download_pe():
    """更新沪深300 PE数据 — 使用 akshare stock_index_pe_lg"""
    try:
        import akshare as ak
        df = ak.stock_index_pe_lg(symbol="沪深300")
        if df is not None and len(df) > 0:
            print(f"  PE: got {len(df)} rows, latest {df['日期'].iloc[-1]}")
            return df
    except Exception as e:
        print("  PE: failed -", str(e)[:80])
    return None


def _download_m2():
    """下载 M2 货币供应量（月末数据）"""
    try:
        import akshare as ak
        df = ak.macro_china_money_supply()
        if df is not None and len(df) > 0:
            print(f"  M2: got {len(df)} rows, latest {df['月份'].iloc[0]}")
            return df
    except Exception as e:
        print("  M2: failed -", str(e)[:80])
    return None


def _download_pmi():
    """下载 PMI 制造业采购经理指数"""
    try:
        import akshare as ak
        df = ak.macro_china_pmi()
        if df is not None and len(df) > 0:
            print(f"  PMI: got {len(df)} rows")
            return df
    except Exception as e:
        print("  PMI: failed -", str(e)[:80])
    return None


def _download_cpi():
    """下载 CPI 居民消费价格指数"""
    try:
        import akshare as ak
        df = ak.macro_china_cpi()
        if df is not None and len(df) > 0:
            print(f"  CPI: got {len(df)} rows, latest {df['月份'].iloc[0]}")
            return df
    except Exception as e:
        print("  CPI: failed -", str(e)[:80])
    return None


def _parse_cn_month(val):
    """解析中文月份格式: '2026年06月份' → Timestamp, '2026-06-01'"""
    if isinstance(val, pd.Timestamp):
        return val
    s = str(val).strip()
    # 尝试 "YYYY年MM月份"
    if '年' in s and '月' in s:
        import re
        m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', s)
        if m:
            return pd.Timestamp(f"{m.group(1)}-{m.group(2).zfill(2)}-01")
    # 直接解析
    return pd.Timestamp(s)


def _find_file(code):
    """根据代码找到对应的 .day 文件路径"""
    _build_macro_index()
    from api.day_reader import _MACRO_INDEX
    code_u = code.upper()
    if code_u in _MACRO_INDEX:
        return _MACRO_INDEX[code_u]
    for k, v in _MACRO_INDEX.items():
        if k.startswith(code_u) or code_u.startswith(k):
            return v
    return None


def _download_northbound():
    """下载北向资金日频净流入数据"""
    try:
        import akshare as ak
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is not None and len(df) > 0:
            print(f"  北向资金: got {len(df)} rows, latest {df['日期'].iloc[-1]}")
            return df
    except Exception as e:
        print(f"  北向资金: failed - {str(e)[:80]}")
    return None


def _download_lockup():
    """下载限售解禁数据（未来解禁市值）"""
    try:
        import akshare as ak
        df = ak.stock_restricted_release_queue_em()
        if df is not None and len(df) > 0:
            print(f"  限售解禁: got {len(df)} rows, latest {df['日期'].iloc[0] if '日期' in df.columns else 'N/A'}")
            return df
    except Exception as e:
        print(f"  限售解禁: failed - {str(e)[:80]}")
    return None


def _download_rzrq():
    """下载融资融券余额（用沪市历史数据，深市只有快照）"""
    try:
        import akshare as ak
        df = ak.stock_margin_sse()
        if df is not None and len(df) > 0:
            print(f"  融资融券(SH): got {len(df)} rows")
            return df
    except Exception as e:
        print(f"  融资融券: failed - {str(e)[:80]}")
    return None


def _download_bond_yield():
    """下载中国10年期国债收益率"""
    try:
        import akshare as ak
        df = ak.bond_china_yield()
        if df is not None and len(df) > 0:
            print(f"  国债收益率: got {len(df)} rows")
            return df
    except Exception as e:
        print(f"  国债收益率: failed - {str(e)[:80]}")
    return None


def _download_sectors():
    """下载申万一级行业指数数据，映射到 990xxx .day 文件"""
    # SW 代码 → MarketPulse 990xxx 映射
    SW_TO_990 = {
        '801010': '990001',  # 农林牧渔
        '801020': '990002',  # 采掘 (可能已停更)
        '801030': '990003',  # 化工
        '801040': '990004',  # 钢铁
        '801050': '990005',  # 有色金属
        '801080': '990006',  # 电子
        '801110': '990007',  # 家用电器
        '801120': '990008',  # 食品饮料
        '801130': '990009',  # 纺织服装
        '801140': '990010',  # 轻工制造
        '801150': '990011',  # 医药生物
        '801160': '990012',  # 公用事业
        '801170': '990013',  # 交通运输
        '801180': '990014',  # 房地产
        '801200': '990015',  # 商业贸易
        '801210': '990016',  # 休闲服务
        '801230': '990017',  # 综合
        '801710': '990018',  # 建筑材料
        '801720': '990019',  # 建筑装饰
        '801730': '990020',  # 电气设备
        '801740': '990021',  # 国防军工
        '801750': '990022',  # 计算机
        '801760': '990023',  # 传媒
        '801770': '990024',  # 通信
        '801780': '990025',  # 银行
        '801790': '990026',  # 非银金融
        '801880': '990027',  # 汽车
        '801890': '990028',  # 机械设备
    }

    import akshare as ak
    added_total = 0
    for sw_code, mp_code in SW_TO_990.items():
        try:
            df = ak.index_hist_sw(symbol=sw_code)
            if df is None or len(df) == 0:
                continue
            # Check if data is recent (within 30 days)
            latest_date = pd.Timestamp(df['日期'].iloc[-1])
            if (pd.Timestamp.now() - latest_date).days > 30:
                continue  # Skip stale codes

            path = _find_file(mp_code)
            if path is None:
                continue

            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": pd.Timestamp(row['日期']),
                    "open": float(row['开盘']),
                    "high": float(row['最高']),
                    "low": float(row['最低']),
                    "close": float(row['收盘']),
                    "amount": float(row.get('成交额', 0)),
                    "volume": float(row.get('成交量', 0)),
                })
            added = _append_to_day(path, records)
            added_total += added
        except Exception:
            continue

    return added_total


def _download_market_volume():
    """下载沪深300日线（含成交额），作为全市场成交额的 proxy"""
    try:
        import urllib.request, json
        # Sina API 获取沪深300日线
        url = ('https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
               'CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=no&datalen=2000')
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode('gbk', errors='ignore')
        data = json.loads(text)
        if data:
            import pandas as pd
            records = []
            for item in data:
                records.append({
                    "date": pd.Timestamp(item["day"]),
                    "close": float(item.get("volume", 0)),  # 成交额用成交量代替（等比例即可）
                })
            df = pd.DataFrame(records).sort_values("date")
            print(f"  沪深300日线(Sina): got {len(df)} rows, latest {df['date'].iloc[-1].date()}")
            return df
    except Exception as e:
        print(f"  成交额(Sina): failed - {str(e)[:80]}")
    return None


def run_update(check_only=False):
    """执行增量更新"""
    print(f"\n{'='*50}")
    print(f"  A-Index 数据更新 — {date.today()}")
    print(f"{'='*50}")
    total_added = 0

    # 1. 汇率 RMBUS
    print("\n[汇率]")
    df = _download_rmb()
    if df is not None and not check_only:
        path = _find_file("RMBUS")
        if path:
            records = []
            for _, row in df.iterrows():
                try:
                    dt = row.get("日期") or row.get("date") or row.iloc[0]
                    if isinstance(dt, str):
                        dt = pd.Timestamp(dt)
                    # currency_boc_safe 返回 '美元' 列，值如 679.34 = 6.7934 CNY/USD
                    close = float(row.get("美元", row.get("close", row.iloc[1]))) / 100.0
                    records.append({"date": dt, "close": close})
                except:
                    continue
            added = _append_to_day(path, records)
            total_added += added
            print(f"  RMBUS: +{added} records")

    # 2. SHIBOR
    print("\n[SHIBOR]")
    df = _download_shibor()
    if df is not None and not check_only:
        path = _find_file("SHIBOR")
        if path:
            records = []
            for _, row in df.iterrows():
                try:
                    dt = row.get("日期") or row.get("date") or row.iloc[0]
                    if isinstance(dt, str): dt = pd.Timestamp(dt)
                    cols = df.columns.tolist()
                    on_col = next((c for c in cols if 'O/N' in str(c) or 'ON' in str(c).upper() or '隔夜' in str(c)), cols[1] if len(cols)>1 else cols[0])
                    close = float(row[on_col] if on_col in row.index else row.iloc[-1])
                    records.append({"date": dt, "close": close})
                except:
                    continue
            added = _append_to_day(path, records)
            total_added += added
            print(f"  SHIBOR: +{added} records")

    # 3. PE (parquet)
    print("\n[PE]")
    df = _download_pe()
    if df is not None and not check_only:
        from config import PE_CACHE_PATH
        try:
            # stock_index_pe_lg 返回: 日期, 滚动市盈率
            new_df = pd.DataFrame({
                "date": pd.to_datetime(df["日期"]),
                "pe": pd.to_numeric(df["滚动市盈率"], errors="coerce"),
            }).dropna()
            new_df = new_df.sort_values("date")
            new_df.to_parquet(PE_CACHE_PATH, index=False)
            print(f"  PE: {len(new_df)} rows saved, latest {new_df['date'].iloc[-1].strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"  PE: save failed - {e}")

    # 4. M2 货币供应量（同比增速）
    print("\n[M2]")
    df = _download_m2()
    if df is not None and not check_only:
        path = _find_file("M2")
        if path:
            records = []
            for _, row in df.iterrows():
                try:
                    dt = _parse_cn_month(row.iloc[0])
                    # 取"M2 同比增长"列
                    cols = df.columns.tolist()
                    m2_col = next((c for c in cols if 'M2' in str(c).upper() and '同比' in str(c)), None)
                    if m2_col is None:
                        m2_col = next((c for c in cols if 'M2' in str(c).upper()), cols[1] if len(cols) > 1 else cols[0])
                    val = float(row[m2_col])
                    records.append({"date": dt, "close": val})
                except:
                    continue
            added = _append_to_day(path, records)
            total_added += added
            print(f"  M2: +{added} records")

    # 5. PMI 制造业指数
    print("\n[PMI]")
    df = _download_pmi()
    if df is not None and not check_only:
        path = _find_file("PMI")
        if path:
            records = []
            for _, row in df.iterrows():
                try:
                    dt = _parse_cn_month(row.iloc[0])
                    val = float(row["制造业-指数"])
                    records.append({"date": dt, "close": val})
                except:
                    continue
            added = _append_to_day(path, records)
            total_added += added
            print(f"  PMI: +{added} records")

    # 6. CPI 全国当月同比
    print("\n[CPI]")
    df = _download_cpi()
    if df is not None and not check_only:
        path = _find_file("CPI")
        if path:
            records = []
            expected_col = "全国-同比增长" if "全国-同比增长" in (df.columns if df is not None else []) else None
            for _, row in df.iterrows():
                try:
                    dt = _parse_cn_month(row.iloc[0])
                    if expected_col and expected_col in row.index:
                        val = float(row[expected_col])
                    else:
                        val = float(row.iloc[1])
                    records.append({"date": dt, "close": val})
                except:
                    continue
            added = _append_to_day(path, records)
            total_added += added
            print(f"  CPI: +{added} records")

    # 7. 北向资金 (TRNBD)
    print("\n[北向资金]")
    df = _download_northbound()
    if df is not None and not check_only:
        path = _find_file("TRNBD")
        if path is None:
            path = MACRO_DATA_DIR / "38#7_TRNBD.day"
        records = []
        for _, row in df.iterrows():
            try:
                dt = row.get("日期") or row.get("date") or row.iloc[0]
                if isinstance(dt, str):
                    dt = pd.Timestamp(dt)
                net_flow = float(row.get("当日成交净买额", row.get("净流入", row.iloc[1])))
                records.append({"date": dt, "close": net_flow})
            except:
                continue
        added = _append_to_day(path, records)
        total_added += added
        print(f"  TRNBD: +{added} records")

    # 8. 限售解禁
    print("\n[限售解禁]")
    df = _download_lockup()
    if df is not None and not check_only:
        path = _find_file("LOCKUP")
        if path is None:
            path = MACRO_DATA_DIR / "38#7_LOCKUP.day"
        records = []
        for _, row in df.iterrows():
            try:
                dt = row.get("解禁时间") or row.get("日期") or row.get("date") or row.iloc[1]
                if isinstance(dt, str):
                    dt = pd.Timestamp(dt)
                val = float(row.get("实际解禁数量市值", row.get("解禁市值", row.get("市值", row.iloc[6]))))
                records.append({"date": dt, "close": val})
            except:
                continue
        added = _append_to_day(path, records)
        total_added += added
        print(f"  LOCKUP: +{added} records")

    # 9. 融资融券余额 (沪市)
    print("\n[融资融券]")
    df = _download_rzrq()
    if df is not None and not check_only:
        for col, code in [("融资余额", "RZ"), ("融券余量金额", "RQ")]:
            if col not in df.columns:
                continue
            path = _find_file(code)
            if path is None:
                path = MACRO_DATA_DIR / f"38#7_{code}.day"
            records = []
            date_col = "信用交易日期" if "信用交易日期" in df.columns else "日期"
            for _, row in df.iterrows():
                try:
                    dt = row.get(date_col) or row.iloc[0]
                    if isinstance(dt, str): dt = pd.Timestamp(dt)
                    val = float(row[col])
                    records.append({"date": dt, "close": val})
                except:
                    continue
            if records:
                added = _append_to_day(path, records)
                total_added += added
                print(f"  {code}: +{added} records")

    # 10. 国债收益率
    print("\n[国债收益率]")
    df = _download_bond_yield()
    if df is not None and not check_only:
        path = _find_file("CNTY")
        if path is None:
            path = MACRO_DATA_DIR / "38#5_CNTY.day"
        records = []
        for _, row in df.iterrows():
            try:
                dt = row.get("日期") or row.get("date") or row.iloc[0]
                if isinstance(dt, str): dt = pd.Timestamp(dt)
                # 取10年期
                if "10年" in str(df.columns):
                    col_10y = next((c for c in df.columns if "10年" in str(c)), df.columns[1])
                    val = float(row[col_10y])
                else:
                    val = float(row.iloc[1])
                records.append({"date": dt, "close": val})
            except:
                continue
        added = _append_to_day(path, records)
        total_added += added
        print(f"  CNTY: +{added} records")

    # 11. 全市场成交额 (用 Sina 沪深300成交量)
    print("\n[成交额]")
    df = _download_market_volume()
    if df is not None and not check_only:
        path = _find_file("TRD")
        if path is None:
            path = MACRO_DATA_DIR / "38#5_TRD.day"
        records = []
        for _, row in df.iterrows():
            try:
                dt = row["date"]
                if isinstance(dt, str): dt = pd.Timestamp(dt)
                val = float(row["close"])  # 成交量作为成交额 proxy
                if val and val > 0:
                    records.append({"date": dt, "close": val})
            except:
                continue
        added = _append_to_day(path, records)
        total_added += added
        print(f"  TRD: +{added} records")

    # 12. 行业指数 (从申万同步)
    print("\n[行业指数]")
    sector_added = _download_sectors()
    total_added += sector_added
    print(f"  行业指数: +{sector_added} records")

    print(f"\n{'='*50}")
    print(f"  总计新增 {total_added} 条记录")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="A-Index 数据更新")
    p.add_argument("--check", action="store_true", help="只检查不写入")
    args = p.parse_args()
    run_update(check_only=args.check)
