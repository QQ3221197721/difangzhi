"""
地方志数据智能管理系统 - 核心模块初始化
"""
from app.core.config import settings, get_settings
from app.core.database import get_db, init_db, close_db, Base

__all__ = [
    "settings",
    "get_settings",
    "get_db",
    "init_db",
    "close_db",
    "Base",
]
