@echo off
chcp 65001 >nul
cd /d %~dp0
title 养成 - 一键启动

set "APP_PORT=18730"
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if /i "%%~A"=="APP_PORT" if not "%%~B"=="" set "APP_PORT=%%~B"
    )
)

echo [检测] 检查服务是否已在运行...
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',%APP_PORT%); $c.Close(); exit 0 } catch { exit 1 }"
if not errorlevel 1 (
    echo [提示] 服务已在运行，直接打开网页。
    start "" http://127.0.0.1:%APP_PORT%
    exit /b 0
)

if not exist "backend\.venv\Scripts\python.exe" (
    echo [初始化] 未找到后端虚拟环境，正在创建...
    pushd backend
    uv venv --python 3.14
    if errorlevel 1 (
        popd
        echo [错误] 虚拟环境创建失败，请检查是否已安装 uv。
        pause
        exit /b 1
    )
    uv pip install -r requirements.txt
    if errorlevel 1 (
        popd
        echo [错误] 依赖安装失败。
        pause
        exit /b 1
    )
    popd
    if not exist "backend\.venv\Scripts\python.exe" (
        echo [错误] 后端环境创建失败，请检查是否已安装 uv。
        pause
        exit /b 1
    )
)

set "NEED_BUILD=0"
if not exist "frontend\dist\index.html" set "NEED_BUILD=1"
if not exist "frontend\node_modules" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" (
    powershell -NoProfile -Command "$dist=(Get-Item 'frontend\dist\index.html').LastWriteTimeUtc; $src=Get-ChildItem 'frontend\src','frontend\index.html','frontend\vite.config.js','frontend\package.json','frontend\package-lock.json' -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTimeUtc -gt $dist }; if ($src) { exit 0 } else { exit 1 }"
    if not errorlevel 1 set "NEED_BUILD=1"
)

if "%NEED_BUILD%"=="1" (
    echo [构建] 前端需要构建，正在执行 npm run build...
    pushd frontend
    if not exist "node_modules" call npm install
    call npm run build
    if errorlevel 1 (
        popd
        echo [错误] 前端构建失败，请检查 Node 环境。
        pause
        exit /b 1
    )
    popd
) else (
    echo [跳过] 前端构建产物已是最新。
)

echo [启动] 服务启动中...
start "养成-服务" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe main.py"

echo [等待] 等待服务就绪（最多 30 秒）...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(30); while((Get-Date) -lt $deadline){ try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',%APP_PORT%); $c.Close(); exit 0 } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 (
    echo [提示] 服务启动较慢，请稍后手动打开 http://127.0.0.1:%APP_PORT%
) else (
    echo [完成] 已打开 http://127.0.0.1:%APP_PORT%
    start "" http://127.0.0.1:%APP_PORT%
)
exit /b 0
