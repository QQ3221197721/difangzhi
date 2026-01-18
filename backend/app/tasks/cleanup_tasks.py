"""
清理和维护任务
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import os

logger = get_task_logger(__name__)


@shared_task
def cleanup_expired_files():
    """清理过期上传文件（保留30天）"""
    from app.celery_app import run_async
    from app.core.database import AsyncSessionLocal
    from app.core.config import settings
    from app.models.models import FileUpload
    from sqlalchemy import select, delete
    
    async def _cleanup():
        async with AsyncSessionLocal() as db:
            # 30天前的文件
            expire_date = datetime.utcnow() - timedelta(days=30)
            
            result = await db.execute(
                select(FileUpload).where(
                    FileUpload.created_at < expire_date,
                    FileUpload.status == "completed"
                )
            )
            files = result.scalars().all()
            
            deleted_count = 0
            for file in files:
                # 删除物理文件
                if os.path.exists(file.file_path):
                    try:
                        os.remove(file.file_path)
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除文件失败: {file.file_path}, {e}")
            
            # 更新数据库状态
            await db.execute(
                delete(FileUpload).where(
                    FileUpload.created_at < expire_date,
                    FileUpload.status == "completed"
                )
            )
            await db.commit()
            
            logger.info(f"清理完成，删除 {deleted_count} 个过期文件")
            return {"deleted": deleted_count}
    
    return run_async(_cleanup())


@shared_task
def update_search_statistics():
    """更新搜索统计"""
    from app.celery_app import run_async
    from app.core.database import AsyncSessionLocal, get_redis
    from app.models.models import ChronicleRecord
    from sqlalchemy import select, func
    
    async def _update():
        async with AsyncSessionLocal() as db:
            redis = await get_redis()
            
            # 统计总记录数
            result = await db.execute(select(func.count(ChronicleRecord.id)))
            total = result.scalar()
            await redis.set("stats:total_records", total)
            
            # 统计各工作类别数量
            result = await db.execute(
                select(ChronicleRecord.work_category, func.count(ChronicleRecord.id))
                .group_by(ChronicleRecord.work_category)
            )
            for category, count in result.all():
                if category:
                    await redis.hset("stats:by_category", category, count)
            
            # 统计各年份数量
            result = await db.execute(
                select(ChronicleRecord.year, func.count(ChronicleRecord.id))
                .group_by(ChronicleRecord.year)
            )
            for year, count in result.all():
                if year:
                    await redis.hset("stats:by_year", str(year), count)
            
            logger.info("搜索统计更新完成")
            return {"total": total}
    
    return run_async(_update())


@shared_task
def optimize_database():
    """优化数据库"""
    from app.celery_app import run_async
    from app.core.database import engine
    from sqlalchemy import text
    
    async def _optimize():
        async with engine.begin() as conn:
            # 更新统计信息
            await conn.execute(text("ANALYZE chronicle_records"))
            await conn.execute(text("ANALYZE users"))
            await conn.execute(text("ANALYZE file_uploads"))
            
            # 重建索引（生产环境谨慎使用）
            # await conn.execute(text("REINDEX TABLE chronicle_records"))
            
            logger.info("数据库优化完成")
            return {"status": "completed"}
    
    return run_async(_optimize())


@shared_task
def cleanup_audit_logs():
    """清理90天前的审计日志"""
    from app.celery_app import run_async
    from app.core.database import AsyncSessionLocal
    from app.models.models import AuditLog
    from sqlalchemy import delete
    
    async def _cleanup():
        async with AsyncSessionLocal() as db:
            expire_date = datetime.utcnow() - timedelta(days=90)
            
            result = await db.execute(
                delete(AuditLog).where(AuditLog.created_at < expire_date)
            )
            await db.commit()
            
            logger.info(f"清理 {result.rowcount} 条审计日志")
            return {"deleted": result.rowcount}
    
    return run_async(_cleanup())
