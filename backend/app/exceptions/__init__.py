# 地方志数据智能管理系统 - 异常模块
"""自定义异常类和异常处理"""

from .exceptions import (
    BaseAPIException,
    BadRequestException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ConflictException,
    ValidationException,
    RateLimitException,
    ServiceUnavailableException,
    DatabaseException,
    FileException,
    AIServiceException,
)
from .handlers import (
    register_exception_handlers,
    api_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)

__all__ = [
    # 异常类
    "BaseAPIException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ConflictException",
    "ValidationException",
    "RateLimitException",
    "ServiceUnavailableException",
    "DatabaseException",
    "FileException",
    "AIServiceException",
    # 处理器
    "register_exception_handlers",
    "api_exception_handler",
    "validation_exception_handler",
    "generic_exception_handler",
]
