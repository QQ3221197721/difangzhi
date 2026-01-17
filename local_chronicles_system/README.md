# 地方志数据管理系统

## 系统架构

```
├── backend/                 # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── utils/          # 工具函数
│   └── requirements.txt
├── frontend/               # 前端应用 (React)
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── pages/          # 页面
│   │   ├── services/       # API服务
│   │   └── styles/         # 样式
│   └── package.json
├── docker/                 # Docker配置
└── docs/                   # 文档
```

## 技术栈

- **后端**: FastAPI + PostgreSQL + Redis + Celery
- **前端**: React + Ant Design (阿里云风格)
- **AI**: OpenAI API / 本地大模型
- **部署**: Docker + Nginx + Gunicorn

## 快速启动

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm start
```
