"""
地方志数据智能管理系统 - AI 异步任务
"""
import asyncio
from celery import shared_task
import structlog

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=3)
def process_document_task(self, document_id: int):
    """处理文档任务 - 提取内容、生成摘要、创建嵌入向量"""
    try:
        # 在异步上下文中运行
        asyncio.run(_process_document_async(document_id))
        logger.info(f"Document {document_id} processed successfully")
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        self.retry(exc=e, countdown=60)


async def _process_document_async(document_id: int):
    """异步处理文档"""
    from app.core.database import get_db_context
    from app.models import Document
    from app.services.storage_service import storage_service
    from app.services.file_processor import file_processor
    from app.services.ai_service import ai_service
    from sqlalchemy import select
    
    async with get_db_context() as db:
        # 获取文档
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        
        if not document:
            logger.warning(f"Document {document_id} not found")
            return
        
        # 1. 如果有文件，提取内容
        if document.file_path:
            content = await storage_service.download_file(document.file_path)
            extracted = await file_processor.extract_content(document.file_path, content)
            
            if "error" not in extracted:
                document.content = extracted.get("content")
                document.full_text = extracted.get("full_text")
        
        # 2. 生成 AI 摘要和关键词
        text_to_analyze = document.full_text or document.content
        if text_to_analyze:
            summary_result = await ai_service.summarize(text_to_analyze)
            document.ai_summary = summary_result.get("summary")
            document.ai_keywords = summary_result.get("keywords", [])
            
            # 3. 生成嵌入向量
            embedding = await ai_service.get_embedding(
                f"{document.title} {document.ai_summary or document.content or ''}"
            )
            if embedding:
                document.embedding = embedding
        
        await db.commit()
        logger.info(f"Document {document_id} processing completed")


@shared_task(bind=True, max_retries=3)
def generate_embedding_task(self, document_id: int):
    """为文档生成嵌入向量"""
    try:
        asyncio.run(_generate_embedding_async(document_id))
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        self.retry(exc=e, countdown=60)


async def _generate_embedding_async(document_id: int):
    """异步生成嵌入向量"""
    from app.core.database import get_db_context
    from app.models import Document
    from app.services.ai_service import ai_service
    from sqlalchemy import select
    
    async with get_db_context() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        
        if not document:
            return
        
        text = f"{document.title} {document.content or document.ai_summary or ''}"
        embedding = await ai_service.get_embedding(text)
        
        if embedding:
            document.embedding = embedding
            await db.commit()


@shared_task
def batch_process_documents_task(document_ids: list):
    """批量处理文档"""
    results = []
    for doc_id in document_ids:
        try:
            asyncio.run(_process_document_async(doc_id))
            results.append({"document_id": doc_id, "status": "success"})
        except Exception as e:
            results.append({"document_id": doc_id, "status": "error", "error": str(e)})
    return results
