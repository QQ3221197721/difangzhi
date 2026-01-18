"""
地方志数据智能管理系统 - 数据模型初始化
"""
from app.models.models import (
    User, UserRole,
    LoginLog,
    Category,
    Document, DocumentCategory, DataStatus,
    AIChat,
    OperationLog,
)

__all__ = [
    "User", "UserRole",
    "LoginLog",
    "Category",
    "Document", "DocumentCategory", "DataStatus",
    "AIChat",
    "OperationLog",
]
