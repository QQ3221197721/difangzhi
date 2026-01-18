"""地方志数据智能管理系统 - Celery 任务模块"""

from app.tasks.ai_tasks import (
    process_document_ai,
    generate_document_summary,
    extract_document_keywords,
    generate_document_embedding,
)
from app.tasks.file_tasks import (
    process_uploaded_file,
    cleanup_temp_files,
)
from app.tasks.cleanup_tasks import (
    cleanup_expired_sessions,
    cleanup_old_logs,
    archive_old_documents,
)

__all__ = [
    # AI 任务
    "process_document_ai",
    "generate_document_summary",
    "extract_document_keywords",
    "generate_document_embedding",
    # 文件任务
    "process_uploaded_file",
    "cleanup_temp_files",
    # 清理任务
    "cleanup_expired_sessions",
    "cleanup_old_logs",
    "archive_old_documents",
]
