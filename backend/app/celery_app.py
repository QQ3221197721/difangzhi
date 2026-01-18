"""
Celery异步任务配置和任务定义
"""
from celery import Celery
from celery.schedules import crontab
import asyncio
from app.core.config import settings

# 创建Celery应用
celery_app = Celery(
    "local_chronicles",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.file_tasks", "app.tasks.ai_tasks", "app.tasks.cleanup_tasks"]
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务配置
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    task_soft_time_limit=3000,  # 50分钟软超时
    
    # 结果配置
    result_expires=86400,  # 结果保留24小时
    
    # 并发配置
    worker_concurrency=4,
    worker_prefetch_multiplier=2,
    
    # 重试配置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 任务路由
    task_routes={
        "app.tasks.file_tasks.*": {"queue": "file_processing"},
        "app.tasks.ai_tasks.*": {"queue": "ai_processing"},
        "app.tasks.cleanup_tasks.*": {"queue": "cleanup"},
    },
    
    # 定时任务
    beat_schedule={
        # 每天凌晨2点清理过期文件
        "cleanup-expired-files": {
            "task": "app.tasks.cleanup_tasks.cleanup_expired_files",
            "schedule": crontab(hour=2, minute=0),
        },
        # 每小时更新搜索统计
        "update-search-stats": {
            "task": "app.tasks.cleanup_tasks.update_search_statistics",
            "schedule": crontab(minute=0),
        },
        # 每天凌晨3点优化数据库
        "optimize-database": {
            "task": "app.tasks.cleanup_tasks.optimize_database",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)


def run_async(coro):
    """在Celery中运行异步函数"""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)
