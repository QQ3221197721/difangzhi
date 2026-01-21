@echo off
REM 地方志数据智能管理系统 - 一键管理脚本 (Windows)
REM ================================================

setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%

if "%1"=="" goto :usage
if "%1"=="help" goto :usage
if "%1"=="install" goto :install
if "%1"=="dev" goto :dev
if "%1"=="start" goto :start
if "%1"=="stop" goto :stop
if "%1"=="test" goto :test
if "%1"=="build" goto :build
if "%1"=="migrate" goto :migrate
if "%1"=="init-db" goto :init_db
if "%1"=="backup" goto :backup
if "%1"=="health" goto :health
if "%1"=="logs" goto :logs
if "%1"=="clean" goto :clean
if "%1"=="vectorize" goto :vectorize
if "%1"=="models" goto :models
if "%1"=="export" goto :export
goto :usage

:usage
echo.
echo ===== 地方志数据智能管理系统 =====
echo.
echo Usage: run.bat [command]
echo.
echo Commands:
echo   install     安装所有依赖
echo   dev         启动开发环境
echo   start       启动生产服务 (Docker Compose)
echo   stop        停止所有服务
echo   test        运行测试
echo   build       构建Docker镜像
echo   migrate     运行数据库迁移
echo   init-db     初始化数据库
echo   backup      备份数据
echo   health      健康检查
echo   logs        查看日志
echo   clean       清理临时文件
echo   vectorize   文档向量化
echo   models      模型管理
echo   export      导出数据
echo   help        显示帮助
echo.
goto :eof

:install
echo Installing dependencies...
echo.

echo [1/3] Installing backend dependencies...
cd backend
pip install -r requirements.txt
cd ..

echo [2/3] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo [3/3] Creating directories...
if not exist "backend\uploads" mkdir backend\uploads
if not exist "backend\logs" mkdir backend\logs

echo.
echo Installation complete!
goto :eof

:dev
echo Starting development environment...
echo.

REM 启动后端
start "Backend" cmd /k "cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM 启动前端
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Development servers started:
echo   - Backend: http://localhost:8000
echo   - Frontend: http://localhost:5173
echo   - API Docs: http://localhost:8000/docs
echo.
goto :eof

:start
echo Starting production services with Docker Compose...
docker-compose up -d
echo.
echo Services started:
echo   - Frontend: http://localhost
echo   - Backend API: http://localhost/api
echo.
goto :eof

:stop
echo Stopping all services...
docker-compose down
echo Services stopped.
goto :eof

:test
echo Running tests...
echo.

echo [Backend Tests]
cd backend
pytest tests/ -v --cov=app
cd ..

echo.
echo [Frontend Build Check]
cd frontend
call npm run build
cd ..

echo.
echo Tests complete!
goto :eof

:build
echo Building Docker images...
docker-compose build
echo Build complete!
goto :eof

:migrate
echo Running database migrations...
cd backend
alembic upgrade head
cd ..
echo Migrations complete!
goto :eof

:init_db
echo Initializing database...
cd backend
python scripts/init_db.py
cd ..
echo Database initialized!
goto :eof

:backup
echo Running backup...
cd backend
python scripts/backup.py
cd ..
echo Backup complete!
goto :eof

:health
echo Running health check...
cd backend
python scripts/health_check.py
cd ..
goto :eof

:logs
echo Showing logs...
if "%2"=="" (
    docker-compose logs -f --tail=100
) else (
    docker-compose logs -f --tail=100 %2
)
goto :eof

:clean
echo Cleaning temporary files...

REM Python缓存
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
for /r . %%f in (*.pyc) do @if exist "%%f" del "%%f"

REM 测试缓存
if exist backend\.pytest_cache rd /s /q backend\.pytest_cache
if exist backend\htmlcov rd /s /q backend\htmlcov

REM 前端缓存
if exist frontend\node_modules\.cache rd /s /q frontend\node_modules\.cache
if exist frontend\dist rd /s /q frontend\dist

echo Clean complete!
goto :eof

:vectorize
echo Running document vectorization...
echo.
cd backend
if "%2"=="--force" (
    python scripts/vectorize.py --force
) else (
    python scripts/vectorize.py
)
cd ..
echo Vectorization complete!
goto :eof

:models
echo Model management...
echo.
cd backend
if "%2"=="" (
    python scripts/model_manager.py list
) else (
    python scripts/model_manager.py %2 %3 %4
)
cd ..
goto :eof

:export
echo Exporting data...
echo.
if "%2"=="" (
    echo Usage: run.bat export [output_file] [--format json^|csv^|jsonl] [--type documents^|categories^|training]
    goto :eof
)
cd backend
python scripts/export_data.py -o %2 %3 %4 %5 %6
cd ..
echo Export complete!
goto :eof

:eof
endlocal
