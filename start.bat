@echo off
REM 地方志系统 - Windows 快速启动脚本

echo ==========================================
echo  地方志数据智能管理系统 - 启动脚本
echo ==========================================
echo.

REM 检查 Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Docker，请先安装 Docker Desktop
    pause
    exit /b 1
)

echo [1/3] 启动基础服务 (PostgreSQL, Redis, MinIO)...
docker-compose up -d postgres redis minio
timeout /t 10 >nul

echo [2/3] 启动后端服务...
docker-compose up -d backend celery-worker

echo [3/3] 启动前端服务...
docker-compose up -d frontend

echo.
echo ==========================================
echo  服务启动完成！
echo ==========================================
echo.
echo  前端地址:    http://localhost:3000
echo  后端 API:    http://localhost:8000
echo  API 文档:    http://localhost:8000/docs
echo  MinIO 控制台: http://localhost:9001
echo  Flower:      http://localhost:5555
echo.
echo  默认管理员: admin / Admin@123456
echo.
echo  查看日志: docker-compose logs -f
echo  停止服务: docker-compose down
echo.
pause
