# 地方志数据智能管理系统 - 自定义异常类
"""业务异常定义"""

from typing import Any, Dict, List, Optional


class BaseAPIException(Exception):
    """
    API异常基类
    
    Attributes:
        code: 业务错误码
        message: 错误消息
        status_code: HTTP状态码
        detail: 详细信息
    """
    code: int = 500
    message: str = "服务器内部错误"
    status_code: int = 500
    
    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[int] = None,
        status_code: Optional[int] = None,
        detail: Optional[Any] = None,
        errors: Optional[List[Dict]] = None
    ):
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.detail = detail
        self.errors = errors
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "code": self.code,
            "message": self.message,
            "data": self.detail
        }
        if self.errors:
            result["errors"] = self.errors
        return result


class BadRequestException(BaseAPIException):
    """错误请求异常 - 400"""
    code = 400
    message = "请求参数错误"
    status_code = 400


class UnauthorizedException(BaseAPIException):
    """未授权异常 - 401"""
    code = 401
    message = "未授权访问，请先登录"
    status_code = 401


class ForbiddenException(BaseAPIException):
    """禁止访问异常 - 403"""
    code = 403
    message = "禁止访问，权限不足"
    status_code = 403


class NotFoundException(BaseAPIException):
    """资源不存在异常 - 404"""
    code = 404
    message = "请求的资源不存在"
    status_code = 404
    
    def __init__(self, resource: str = "资源", resource_id: Any = None, **kwargs):
        if resource_id:
            message = f"{resource} (ID: {resource_id}) 不存在"
        else:
            message = f"{resource}不存在"
        super().__init__(message=message, **kwargs)


class ConflictException(BaseAPIException):
    """资源冲突异常 - 409"""
    code = 409
    message = "资源已存在或状态冲突"
    status_code = 409


class ValidationException(BaseAPIException):
    """数据验证异常 - 422"""
    code = 422
    message = "数据验证失败"
    status_code = 422
    
    def __init__(
        self,
        message: str = "数据验证失败",
        errors: Optional[List[Dict]] = None,
        **kwargs
    ):
        super().__init__(message=message, errors=errors, **kwargs)


class RateLimitException(BaseAPIException):
    """请求频率限制异常 - 429"""
    code = 429
    message = "请求过于频繁，请稍后再试"
    status_code = 429
    
    def __init__(
        self,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        self.retry_after = retry_after
        super().__init__(**kwargs)


class ServiceUnavailableException(BaseAPIException):
    """服务不可用异常 - 503"""
    code = 503
    message = "服务暂时不可用"
    status_code = 503


class DatabaseException(BaseAPIException):
    """数据库异常"""
    code = 500
    message = "数据库操作失败"
    status_code = 500
    
    def __init__(
        self,
        message: str = "数据库操作失败",
        operation: Optional[str] = None,
        **kwargs
    ):
        if operation:
            message = f"数据库{operation}操作失败"
        super().__init__(message=message, **kwargs)


class FileException(BaseAPIException):
    """文件操作异常"""
    code = 500
    message = "文件操作失败"
    status_code = 500


class FileUploadException(FileException):
    """文件上传异常"""
    code = 400
    message = "文件上传失败"
    status_code = 400


class FileTypeNotAllowedException(FileException):
    """文件类型不允许异常"""
    code = 400
    message = "不支持的文件类型"
    status_code = 400
    
    def __init__(self, file_type: str, allowed_types: List[str], **kwargs):
        message = f"不支持的文件类型: {file_type}，允许的类型: {', '.join(allowed_types)}"
        super().__init__(message=message, **kwargs)


class FileSizeExceededException(FileException):
    """文件大小超限异常"""
    code = 400
    message = "文件大小超出限制"
    status_code = 400
    
    def __init__(self, max_size: int, **kwargs):
        message = f"文件大小超出限制，最大允许 {max_size / 1024 / 1024:.1f}MB"
        super().__init__(message=message, **kwargs)


class AIServiceException(BaseAPIException):
    """AI服务异常"""
    code = 503
    message = "AI服务暂时不可用"
    status_code = 503


class AIQuotaExceededException(AIServiceException):
    """AI配额超限异常"""
    code = 429
    message = "AI服务配额已用尽"
    status_code = 429


class AuthenticationException(UnauthorizedException):
    """认证异常"""
    pass


class TokenExpiredException(AuthenticationException):
    """Token过期异常"""
    code = 401
    message = "登录已过期，请重新登录"


class InvalidTokenException(AuthenticationException):
    """无效Token异常"""
    code = 401
    message = "无效的认证信息"


class PermissionDeniedException(ForbiddenException):
    """权限拒绝异常"""
    
    def __init__(self, required_permission: str = None, **kwargs):
        if required_permission:
            message = f"需要 {required_permission} 权限"
            kwargs["message"] = message
        super().__init__(**kwargs)


class BusinessException(BaseAPIException):
    """业务逻辑异常"""
    code = 400
    status_code = 400
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, **kwargs)
