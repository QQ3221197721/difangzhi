@echo off
REM 地方志数据管理系统 - Windows启动脚本
REM 支持 Windows 64位 和 麒麟系统（通过WSL）

echo ============================================
echo   地方志数据管理系统 - 启动脚本
echo ============================================
echo.

REM 检查Docker是否安装
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Docker未安装或未启动
    echo 请先安装Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM 检查Docker Compose是否安装
docker-compose --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Docker Compose未安装
    pause
    exit /b 1
)

echo [信息] 检测到Docker环境正常
echo.

REM 选择启动模式
echo 请选择启动模式:
echo   1. 开发模式 (单独启动前后端)
echo   2. 生产模式 (Docker Compose)
echo   3. 仅启动后端
echo   4. 仅启动前端
echo   5. 停止所有服务
echo.

set /p choice=请输入选项 (1-5): 

if "%choice%"=="1" goto dev_mode
if "%choice%"=="2" goto prod_mode
if "%choice%"=="3" goto backend_only
if "%choice%"=="4" goto frontend_only
if "%choice%"=="5" goto stop_all

echo [错误] 无效选项
pause
exit /b 1

:dev_mode
echo.
echo [信息] 启动开发模式...
echo.

REM 创建虚拟环境并安装依赖
if not exist "backend\venv" (
    echo [信息] 创建Python虚拟环境...
    cd backend
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    cd ..
) else (
    call backend\venv\Scripts\activate.bat
)

REM 启动后端
echo [信息] 启动后端服务...
start cmd /k "cd backend && venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM 安装前端依赖并启动
echo [信息] 启动前端服务...
if not exist "frontend\node_modules" (
    cd frontend
    npm install
    cd ..
)
start cmd /k "cd frontend && npm start"

echo.
echo [成功] 开发环境已启动
echo   后端: http://localhost:8000
echo   前端: http://localhost:3000
echo   API文档: http://localhost:8000/docs
echo.
pause
goto end

:prod_mode
echo.
echo [信息] 启动生产模式 (Docker Compose)...
echo.

REM 复制环境变量文件
if not exist "backend\.env" (
    copy backend\.env.example backend\.env
    echo [提示] 请编辑 backend\.env 文件配置环境变量
)

REM 构建并启动
docker-compose up -d --build

echo.
echo [成功] 生产环境已启动
echo   访问地址: http://localhost
echo   API文档: http://localhost/docs
echo.
pause
goto end

:backend_only
echo.
echo [信息] 仅启动后端服务...
cd backend
if not exist "venv" (
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
goto end

:frontend_only
echo.
echo [信息] 仅启动前端服务...
cd frontend
if not exist "node_modules" (
    npm install
)
npm start
goto end

:stop_all
echo.
echo [信息] 停止所有服务...
docker-compose down
echo [成功] 所有服务已停止
pause
goto end

:end
