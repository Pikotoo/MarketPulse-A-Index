@echo off
chcp 65001 >nul
cd /d %~dp0
title MarketPulse — A股市场脉搏

echo.
echo   ███╗   ███╗ █████╗ ██████╗ ██╗  ██╗███████╗████████╗██████╗ ██╗   ██╗██╗   ██╗███████╗
echo   ████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔════╝╚══██╔══╝██╔══██╗██║   ██║██║   ██║██╔════╝
echo   ██╔████╔██║███████║██████╔╝█████╔╝ █████╗     ██║   ██████╔╝██║   ██║██║   ██║███████╗
echo   ██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══╝     ██║   ██╔═══╝ ██║   ██║██║   ██║╚════██║
echo   ██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗███████╗   ██║   ██║     ╚██████╔╝╚██████╔╝███████║
echo   ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝      ╚═════╝  ╚═════╝ ╚══════╝
echo.
echo                         基于公开市场数据深度加工的量化指标
echo.

:: 检查 API Key 是否配置
if "%DASHBOARD_KEY%"=="" (
    echo [提示] 未设置 DASHBOARD_KEY 环境变量，使用默认值
    set "DK=mp-806fac606a6e1ce607ce158175087ca9"
) else (
    set "DK=%DASHBOARD_KEY%"
)

echo [1/3] 启动 API 服务...
start "MarketPulse" /min py -3.11 api\app.py

echo [2/3] 等待服务就绪（约5秒）...
ping -n 6 127.0.0.1 >nul

echo [3/3] 获取市场数据...
echo.
echo ==================================================
echo   A股市场快照
echo ==================================================
echo.

echo 📌 1. PE分位 — 估值贵不贵？
curl -s -H "X-API-Key: %DK%" http://localhost:8898/api/v1/signal/pe-percentile | py -3.11 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'   当前PE: {d[\"value\"]}   分位: {d[\"percentile\"]}%%   判断: {d[\"interpretation\"]}')"
echo.

echo 📌 2. 股债性价比 — 股票vs债券？
curl -s -H "X-API-Key: %DK%" http://localhost:8898/api/v1/signal/erp | py -3.11 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'   ERP: {d[\"value\"]}%%   国债: {d[\"bond_yield_10y\"]}%%   判断: {d[\"interpretation\"]}')"
echo.

echo 📌 3. 宏观评分 — 经济如何？
curl -s -H "X-API-Key: %DK%" http://localhost:8898/api/v1/signal/macro-score | py -3.11 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'   综合分: {d[\"value\"]}/100   判断: {d[\"interpretation\"]}')"
echo.

echo 📌 4. 行业宽度 — 多少行业在涨？
curl -s -H "X-API-Key: %DK%" http://localhost:8898/api/v1/signal/sector-breadth | py -3.11 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f'   宽度: {d[\"above_ma60_count\"]}/{d[\"sector_count\"]} ({d[\"value\"]*100:.1f}%%)   判断: {d[\"interpretation\"]}'); [print(f'     {s[\"name\"]}: {s[\"momentum_60d\"]:+.2f}%%') for s in d['top_5_sectors']]"
echo.

echo ==================================================
echo   ⚠️  仅供研究参考，不构成投资建议
echo ==================================================
echo.
pause
