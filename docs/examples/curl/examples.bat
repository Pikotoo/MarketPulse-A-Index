@echo off
REM MarketPulse API — Windows CMD 快速测试

set API_BASE=http://localhost:8898
set API_KEY=mp-xxxxxxxx

echo ==========================================
echo   MarketPulse API 快速测试
echo   %API_BASE%
echo ==========================================

echo.
echo --- 1. 健康检查 ---
curl -s %API_BASE%/api/v1/health

echo.
echo --- 2. PE 分位 ---
curl -s -H "X-API-Key: %API_KEY%" %API_BASE%/api/v1/signal/pe-percentile

echo.
echo --- 3. ERP 股债性价比 ---
curl -s -H "X-API-Key: %API_KEY%" %API_BASE%/api/v1/signal/erp

echo.
echo --- 4. 宏观综合评分 ---
curl -s -H "X-API-Key: %API_KEY%" %API_BASE%/api/v1/signal/macro-score

echo.
echo --- 5. 行业宽度 ---
curl -s -H "X-API-Key: %API_KEY%" %API_BASE%/api/v1/signal/sector-breadth

echo.
echo ==========================================
echo   测试完成
echo ==========================================
pause
