@echo off
chcp 65001 >nul
cd /d %~dp0
title 养成 - 重置启动

echo 警告：此操作将删除数据库 new_idea 的全部数据（所有存档不可恢复）。
set /p CONFIRM=请输入 YES 确认重置：
if /i not "%CONFIRM%"=="YES" (
    echo 已取消。
    pause
    exit /b 0
)

if "%MYSQL_PASSWORD%"=="" (
    set /p MYSQL_PASSWORD=请输入 MySQL 密码：
)
mysql -u root -p"%MYSQL_PASSWORD%" -e "DROP DATABASE IF EXISTS new_idea;"
if errorlevel 1 (
    echo [错误] 删除数据库失败，请确认 MySQL 已启动且密码正确。
    pause
    exit /b 1
)
echo 数据库已重置。

if not exist "backend\.venv\Scripts\python.exe" (
    echo [提示] 尚未初始化后端环境，请先运行 快速启动.bat。
    pause
    exit /b 1
)

start "养成-服务" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe main.py"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:18730
exit /b 0
