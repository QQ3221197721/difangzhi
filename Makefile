# 地方志数据智能管理系统 - Makefile

.PHONY: help install dev test build docker-up docker-down clean

help:
	@echo "地方志数据智能管理系统 - 可用命令:"
	@echo ""
	@echo "  install      - 安装依赖"
	@echo "  dev          - 启动开发环境"
	@echo "  test         - 运行测试"
	@echo "  build        - 构建生产版本"
	@echo "  docker-up    - 启动 Docker 服务"
	@echo "  docker-down  - 停止 Docker 服务"
	@echo "  clean        - 清理临时文件"
	@echo ""

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "请在两个终端分别运行: make dev-backend 和 make dev-frontend"

test:
	cd backend && pytest -v

test-cov:
	cd backend && pytest --cov=app --cov-report=html

build-frontend:
	cd frontend && npm run build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-rebuild:
	docker-compose up -d --build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

db-migrate:
	cd backend && alembic upgrade head

db-revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"

celery-worker:
	cd backend && celery -A app.celery_app worker --loglevel=info

celery-flower:
	cd backend && celery -A app.celery_app flower --port=5555
