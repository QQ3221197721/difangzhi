# 地方志数据智能管理系统 - 验证模块
"""数据验证器"""

from .validators import (
    validate_email,
    validate_phone,
    validate_id_card,
    validate_password_strength,
    validate_username,
    validate_file_size,
    validate_file_type,
    validate_date_range,
    validate_coordinates,
    ValidationResult,
)
from .decorators import (
    validate_request,
    rate_limit,
)

__all__ = [
    # 验证函数
    "validate_email",
    "validate_phone",
    "validate_id_card",
    "validate_password_strength",
    "validate_username",
    "validate_file_size",
    "validate_file_type",
    "validate_date_range",
    "validate_coordinates",
    "ValidationResult",
    # 装饰器
    "validate_request",
    "rate_limit",
]
