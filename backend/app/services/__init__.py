"""
地方志数据智能管理系统 - 服务模块初始化
"""
from app.services.storage_service import storage_service
from app.services.ai_service import ai_service
from app.services.file_processor import file_processor
from app.services.cache_service import cache_service

__all__ = [
    "storage_service",
    "ai_service",
    "file_processor",
    "cache_service",
]
