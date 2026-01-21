#!/bin/bash
# 地方志数据智能管理系统 - 一键管理脚本 (Linux/Mac)
# ================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo -e "${GREEN}"
    echo "===== 地方志数据智能管理系统 ====="
    echo -e "${NC}"
}

print_usage() {
    print_header
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  install     安装所有依赖"
    echo "  dev         启动开发环境"
    echo "  start       启动生产服务 (Docker Compose)"
    echo "  stop        停止所有服务"
    echo "  test        运行测试"
    echo "  build       构建Docker镜像"
    echo "  migrate     运行数据库迁移"
    echo "  init-db     初始化数据库"
    echo "  backup      备份数据"
    echo "  health      健康检查"
    echo "  logs        查看日志"
    echo "  clean       清理临时文件"
    echo "  help        显示帮助"
    echo ""
}

install_deps() {
    echo -e "${YELLOW}Installing dependencies...${NC}"
    echo ""
    
    echo "[1/3] Installing backend dependencies..."
    cd backend
    pip install -r requirements.txt
    cd ..
    
    echo "[2/3] Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
    
    echo "[3/3] Creating directories..."
    mkdir -p backend/uploads backend/logs
    
    echo -e "${GREEN}Installation complete!${NC}"
}

start_dev() {
    echo -e "${YELLOW}Starting development environment...${NC}"
    
    # 启动后端
    (cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
    BACKEND_PID=$!
    
    # 启动前端
    (cd frontend && npm run dev) &
    FRONTEND_PID=$!
    
    echo ""
    echo -e "${GREEN}Development servers started:${NC}"
    echo "  - Backend: http://localhost:8000"
    echo "  - Frontend: http://localhost:5173"
    echo "  - API Docs: http://localhost:8000/docs"
    echo ""
    echo "Press Ctrl+C to stop..."
    
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
    wait
}

start_prod() {
    echo -e "${YELLOW}Starting production services...${NC}"
    docker-compose up -d
    echo -e "${GREEN}Services started!${NC}"
    echo "  - Frontend: http://localhost"
    echo "  - Backend API: http://localhost/api"
}

stop_services() {
    echo -e "${YELLOW}Stopping all services...${NC}"
    docker-compose down
    echo -e "${GREEN}Services stopped.${NC}"
}

run_tests() {
    echo -e "${YELLOW}Running tests...${NC}"
    
    echo "[Backend Tests]"
    cd backend
    pytest tests/ -v --cov=app
    cd ..
    
    echo ""
    echo "[Frontend Build Check]"
    cd frontend
    npm run build
    cd ..
    
    echo -e "${GREEN}Tests complete!${NC}"
}

build_images() {
    echo -e "${YELLOW}Building Docker images...${NC}"
    docker-compose build
    echo -e "${GREEN}Build complete!${NC}"
}

run_migrations() {
    echo -e "${YELLOW}Running database migrations...${NC}"
    cd backend
    alembic upgrade head
    cd ..
    echo -e "${GREEN}Migrations complete!${NC}"
}

init_database() {
    echo -e "${YELLOW}Initializing database...${NC}"
    cd backend
    python scripts/init_db.py
    cd ..
    echo -e "${GREEN}Database initialized!${NC}"
}

run_backup() {
    echo -e "${YELLOW}Running backup...${NC}"
    cd backend
    python scripts/backup.py
    cd ..
    echo -e "${GREEN}Backup complete!${NC}"
}

run_health_check() {
    echo -e "${YELLOW}Running health check...${NC}"
    cd backend
    python scripts/health_check.py
    cd ..
}

show_logs() {
    service=${2:-""}
    if [ -z "$service" ]; then
        docker-compose logs -f --tail=100
    else
        docker-compose logs -f --tail=100 "$service"
    fi
}

clean_temp() {
    echo -e "${YELLOW}Cleaning temporary files...${NC}"
    
    # Python缓存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # 测试缓存
    rm -rf backend/.pytest_cache backend/htmlcov
    
    # 前端缓存
    rm -rf frontend/node_modules/.cache frontend/dist
    
    echo -e "${GREEN}Clean complete!${NC}"
}

# 主命令处理
case "${1:-help}" in
    install)
        install_deps
        ;;
    dev)
        start_dev
        ;;
    start)
        start_prod
        ;;
    stop)
        stop_services
        ;;
    test)
        run_tests
        ;;
    build)
        build_images
        ;;
    migrate)
        run_migrations
        ;;
    init-db)
        init_database
        ;;
    backup)
        run_backup
        ;;
    health)
        run_health_check
        ;;
    logs)
        show_logs "$@"
        ;;
    clean)
        clean_temp
        ;;
    help|*)
        print_usage
        ;;
esac
