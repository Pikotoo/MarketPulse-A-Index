@echo off
chcp 65001 >nul
cd /d %~dp0
title MarketPulse

echo 正在启动服务...

:: 启动后台服务
start "" /min py -3.11 api\app.py

:: 等待服务就绪
echo 等待服务就绪...
:wait
ping -n 2 127.0.0.1 >nul
curl -s http://localhost:8898/api/v1/health >nul 2>&1
if errorlevel 1 goto wait

:: 打开浏览器
start http://localhost:8898/dashboard

echo.
echo   ✅ 仪表盘已在浏览器中打开！
echo.
echo   如果没自动打开，手动访问：http://localhost:8898/dashboard
echo.
echo   关闭此窗口将停止服务。
echo.
pause

:: 退出前杀掉服务
taskkill /f /im python.exe /fi "WINDOWTITLE eq MarketPulse*" 2>nul
