@echo off
chcp 65001 >nul
cd /d %~dp0
title 养成 - 启动

if not exist "backend\.venv\Scripts\python.exe" (
    echo [初始化] 未找到后端虚拟环境，正在创建...
    pushd backend
    uv venv --python 3.14
    uv pip install -r requirements.txt
    popd
    if not exist "backend\.venv\Scripts\python.exe" (
        echo [错误] 后端环境创建失败，请检查是否已安装 uv。
        pause
        exit /b 1
    )
)

if not exist "frontend\dist\index.html" (
    echo [构建] 未找到前端构建产物，正在安装依赖并构建...
    pushd frontend
    call npm install
    call npm run build
    popd
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
