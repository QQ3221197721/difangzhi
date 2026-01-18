"""
地方志数据智能管理系统 - 主应用入口
完整版：集成认证、文档管理、AI搜索、数据分析
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import structlog
import time
import sys
import os
import uuid

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api import api_router

# 配置结构化日志
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# 确保日志目录存在
os.makedirs("logs", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动地方志数据管理系统...")
    
    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")
    
    yield
    
    # 关闭连接
    await close_db()
    logger.info("系统已关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="地方志数据管理系统 - 支持AI智能提取、双模式搜索、数据分析可视化",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# 添加中间件（顺序很重要）
# 1. Gzip压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Request-ID"]
)




# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志并添加请求ID"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = (time.time() - start_time) * 1000
    
    # 记录日志（排除健康检查）
    if request.url.path not in ["/health", "/"]:
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=round(process_time, 2)
        )
    
    response.headers["X-Process-Time"] = f"{process_time:.2f}"
    response.headers["X-Request-ID"] = request_id
    return response


# 全局异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证错误处理"""
    logger.warning("validation_error", errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": str(exc) if settings.DEBUG else None
        }
    )


# 注册路由
app.include_router(api_router, prefix=settings.API_PREFIX)


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "service": settings.APP_NAME
    }


# 根路径
@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


# API信息
@app.get(f"{settings.API_PREFIX}/info")
async def api_info():
    """API信息"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "endpoints": {
            "auth": f"{settings.API_PREFIX}/auth",
            "documents": f"{settings.API_PREFIX}/documents",
            "categories": f"{settings.API_PREFIX}/categories",
            "ai": f"{settings.API_PREFIX}/ai",
            "analytics": f"{settings.API_PREFIX}/analytics",
            "users": f"{settings.API_PREFIX}/users"
        },
        "features": [
            "实名认证登录",
            "强制位置信息采集",
            "双模数据上传（文件AI提取/手动录入）",
            "多级标签分类体系",
            "AI智能语义搜索",
            "标签筛选搜索",
            "数据分析与可视化",
            "AI助手对话"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS
    )
