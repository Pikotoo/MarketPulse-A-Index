@echo off
chcp 65001 >nul
echo ============================================
echo   MarketPulse 每日定时任务 — 卸载
echo ============================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 请右键「以管理员身份运行」此脚本
    echo.
    pause
    exit /b 1
)

set TASK_NAME=MarketPulse_DailyTask

schtasks /delete /tn "%TASK_NAME%" /f

if %errorlevel% equ 0 (
    echo [成功] 定时任务已删除
) else (
    echo [提示] 任务不存在或已删除
)

pause
