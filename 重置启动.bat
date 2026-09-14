@echo off
chcp 65001 >nul
cd /d %~dp0
title 养成 - 重置启动

echo 警告：此操作将删除数据库的全部数据（所有存档不可恢复）。
set /p CONFIRM=请输入 YES 确认重置：
if /i not "%CONFIRM%"=="YES" (
    echo 已取消。
    pause
    exit /b 0
)

set "MYSQL_HOST=localhost"
set "MYSQL_PORT=3306"
set "MYSQL_USER=root"
set "MYSQL_DATABASE=new_idea"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /i "%%~A"=="MYSQL_HOST" set "MYSQL_HOST=%%~B"
        if /i "%%~A"=="MYSQL_PORT" set "MYSQL_PORT=%%~B"
        if /i "%%~A"=="MYSQL_USER" set "MYSQL_USER=%%~B"
        if /i "%%~A"=="MYSQL_DATABASE" set "MYSQL_DATABASE=%%~B"
        if /i "%%~A"=="MYSQL_PASSWORD" if not defined MYSQL_PASSWORD set "MYSQL_PASSWORD=%%~B"
    )
)

if "%MYSQL_PASSWORD%"=="" set /p MYSQL_PASSWORD=请输入 MySQL 密码：
set "MYSQL_PWD=%MYSQL_PASSWORD%"
mysql --host=%MYSQL_HOST% --port=%MYSQL_PORT% --user=%MYSQL_USER% -e "DROP DATABASE IF EXISTS `%MYSQL_DATABASE%`;"
set "MYSQL_PWD="
if errorlevel 1 (
    echo [错误] 删除数据库失败，请确认 MySQL 已启动且账号密码正确。
    pause
    exit /b 1
)
echo 数据库 %MYSQL_DATABASE% 已重置。

if not exist "backend\.venv\Scripts\python.exe" (
    echo [提示] 尚未初始化后端环境，请先运行 快速启动.bat。
    pause
    exit /b 1
)

echo [启动] 服务启动中...
start "养成-服务" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe main.py"

echo [等待] 等待服务就绪（最多 30 秒）...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(30); while((Get-Date) -lt $deadline){ try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',18730); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 (
    echo [提示] 服务启动较慢，请稍后手动打开 http://127.0.0.1:18730
) else (
    start "" http://127.0.0.1:18730
)
exit /b 0
