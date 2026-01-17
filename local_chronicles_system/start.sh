#!/bin/bash
# 地方志数据管理系统 - Linux/麒麟系统启动脚本

set -e

echo "============================================"
echo "  地方志数据管理系统 - 启动脚本"
echo "============================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}[错误] Docker未安装${NC}"
        echo "请先安装Docker: https://docs.docker.com/engine/install/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}[错误] Docker服务未运行${NC}"
        echo "请启动Docker服务: sudo systemctl start docker"
        exit 1
    fi
    
    echo -e "${GREEN}[信息] Docker环境正常${NC}"
}

# 检查Docker Compose
check_compose() {
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}[错误] Docker Compose未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}[信息] Docker Compose已安装${NC}"
}

# 开发模式
dev_mode() {
    echo -e "${YELLOW}[信息] 启动开发模式...${NC}"
    
    # 后端
    cd backend
    if [ ! -d "venv" ]; then
        echo "[信息] 创建Python虚拟环境..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -r requirements.txt
    
    echo "[信息] 启动后端服务..."
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    cd ..
    
    # 前端
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "[信息] 安装前端依赖..."
        npm install
    fi
    
    echo "[信息] 启动前端服务..."
    npm start &
    FRONTEND_PID=$!
    cd ..
    
    echo ""
    echo -e "${GREEN}[成功] 开发环境已启动${NC}"
    echo "  后端: http://localhost:8000"
    echo "  前端: http://localhost:3000"
    echo "  API文档: http://localhost:8000/docs"
    echo ""
    echo "按 Ctrl+C 停止所有服务"
    
    # 等待退出
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
    wait
}

# 生产模式
prod_mode() {
    echo -e "${YELLOW}[信息] 启动生产模式 (Docker Compose)...${NC}"
    
    # 复制环境变量
    if [ ! -f "backend/.env" ]; then
        cp backend/.env.example backend/.env
        echo -e "${YELLOW}[提示] 请编辑 backend/.env 配置环境变量${NC}"
    fi
    
    docker-compose up -d --build
    
    echo ""
    echo -e "${GREEN}[成功] 生产环境已启动${NC}"
    echo "  访问地址: http://localhost"
    echo "  API文档: http://localhost/docs"
}

# 停止服务
stop_all() {
    echo -e "${YELLOW}[信息] 停止所有服务...${NC}"
    docker-compose down
    echo -e "${GREEN}[成功] 所有服务已停止${NC}"
}

# 查看日志
show_logs() {
    docker-compose logs -f
}

# 显示菜单
show_menu() {
    echo "请选择操作:"
    echo "  1. 开发模式"
    echo "  2. 生产模式 (Docker Compose)"
    echo "  3. 停止所有服务"
    echo "  4. 查看日志"
    echo "  5. 退出"
    echo ""
    read -p "请输入选项 (1-5): " choice
    
    case $choice in
        1) dev_mode ;;
        2) prod_mode ;;
        3) stop_all ;;
        4) show_logs ;;
        5) exit 0 ;;
        *) echo -e "${RED}[错误] 无效选项${NC}"; exit 1 ;;
    esac
}

# 主程序
main() {
    check_docker
    check_compose
    echo ""
    show_menu
}

main "$@"
