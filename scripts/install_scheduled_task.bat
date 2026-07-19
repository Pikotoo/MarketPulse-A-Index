@echo off
chcp 65001 >nul
echo ============================================
echo   MarketPulse 每日定时任务 — 安装
echo ============================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 请右键「以管理员身份运行」此脚本
    echo.
    pause
    exit /b 1
)

set TASK_NAME=MarketPulse_DailyTask
set BAT_PATH=%~dp0daily_task.bat

:: 先删除旧任务（如果存在）
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: 创建新的定时任务
:: /sc DAILY   — 每天执行
:: /st 06:00   — 早上 6:00
:: /ru SYSTEM  — 以 SYSTEM 身份运行（无需登录）
:: /rl HIGHEST — 最高权限
schtasks /create /tn "%TASK_NAME%" ^
  /tr "\"%BAT_PATH%\"" ^
  /sc DAILY /st 06:00 ^
  /ru SYSTEM /rl HIGHEST ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [成功] 定时任务已创建
    echo   任务名称: %TASK_NAME%
    echo   执行时间: 每天 06:00
    echo   执行脚本: %BAT_PATH%
    echo.
    echo 可在「任务计划程序」(taskschd.msc) 中查看和管理
) else (
    echo.
    echo [失败] 任务创建失败，请检查权限
)

pause
