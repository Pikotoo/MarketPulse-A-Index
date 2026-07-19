@echo off
chcp 65001 >nul
cd /d %~dp0..
set PYTHONPATH=%~dp0..

echo [%date% %time%] A-Index 每日任务开始

:: 1. 下载最新数据
echo --- 数据下载 ---
py -3.11 %~dp0download_data.py

:: 2. 预计算所有信号指标
echo --- 信号预计算 ---
py -3.11 %~dp0update_signals.py

:: 3. 数据库备份
echo --- 数据库备份 ---
py -3.11 %~dp0backup_db.py

:: 4. 数据新鲜度检查（异常时写入 .freshness_alert 旗标文件）
echo --- 新鲜度检查 ---
py -3.11 %~dp0check_freshness.py --alert

echo [%date% %time%] 每日任务完成
