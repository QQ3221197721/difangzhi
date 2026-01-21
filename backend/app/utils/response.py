# 地方志数据智能管理系统 - 响应工具
"""统一响应格式构建"""

from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from .pagination import PaginatedResponse, PageInfo

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = Field(default=200, description="响应码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": {}
            }
        }


class PaginatedAPIResponse(BaseModel, Generic[T]):
    """分页API响应格式"""
    code: int = Field(default=200, description="响应码")
    message: str = Field(default="success", description="响应消息")
    data: List[T] = Field(default_factory=list, description="数据列表")
    page_info: PageInfo = Field(description="分页信息")


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = Field(default=None, description="错误字段")
    message: str = Field(description="错误信息")
    code: Optional[str] = Field(default=None, description="错误代码")


class ErrorResponse(BaseModel):
    """错误响应格式"""
    code: int = Field(description="错误码")
    message: str = Field(description="错误消息")
    errors: Optional[List[ErrorDetail]] = Field(default=None, description="错误详情列表")


def success_response(
    data: Any = None,
    message: str = "success",
    code: int = 200
) -> Dict[str, Any]:
    """
    构建成功响应
    
    Args:
        data: 响应数据
        message: 响应消息
        code: 响应码
        
    Returns:
        响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": data
    }


def error_response(
    message: str,
    code: int = 400,
    errors: Optional[List[Dict]] = None,
    data: Any = None
) -> Dict[str, Any]:
    """
    构建错误响应
    
    Args:
        message: 错误消息
        code: 错误码
        errors: 错误详情列表
        data: 附加数据
        
    Returns:
        响应字典
    """
    response = {
        "code": code,
        "message": message,
        "data": data
    }
    
    if errors:
        response["errors"] = errors
    
    return response


def paginated_response(
    paginated: PaginatedResponse,
    message: str = "success",
    code: int = 200
) -> Dict[str, Any]:
    """
    构建分页响应
    
    Args:
        paginated: 分页响应对象
        message: 响应消息
        code: 响应码
        
    Returns:
        响应字典
    """
    return {
        "code": code,
        "message": message,
        "data": paginated.items,
        "page_info": {
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
        }
    }


def json_response(
    data: Any = None,
    message: str = "success",
    code: int = 200,
    status_code: int = 200
) -> JSONResponse:
    """
    构建JSON响应对象
    
    Args:
        data: 响应数据
        message: 响应消息
        code: 业务码
        status_code: HTTP状态码
        
    Returns:
        JSONResponse对象
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": data
        }
    )


def error_json_response(
    message: str,
    code: int = 400,
    status_code: int = 400,
    errors: Optional[List[Dict]] = None
) -> JSONResponse:
    """
    构建错误JSON响应对象
    
    Args:
        message: 错误消息
        code: 业务错误码
        status_code: HTTP状态码
        errors: 错误详情
        
    Returns:
        JSONResponse对象
    """
    content = {
        "code": code,
        "message": message,
        "data": None
    }
    
    if errors:
        content["errors"] = errors
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )


# 常用响应快捷方法
def ok(data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
    """成功响应"""
    return success_response(data=data, message=message)


def created(data: Any = None, message: str = "创建成功") -> Dict[str, Any]:
    """创建成功响应"""
    return success_response(data=data, message=message, code=201)


def deleted(message: str = "删除成功") -> Dict[str, Any]:
    """删除成功响应"""
    return success_response(message=message)


def bad_request(message: str = "请求参数错误") -> Dict[str, Any]:
    """错误请求响应"""
    return error_response(message=message, code=400)


def unauthorized(message: str = "未授权访问") -> Dict[str, Any]:
    """未授权响应"""
    return error_response(message=message, code=401)


def forbidden(message: str = "禁止访问") -> Dict[str, Any]:
    """禁止访问响应"""
    return error_response(message=message, code=403)


def not_found(message: str = "资源不存在") -> Dict[str, Any]:
    """未找到响应"""
    return error_response(message=message, code=404)


def server_error(message: str = "服务器内部错误") -> Dict[str, Any]:
    """服务器错误响应"""
    return error_response(message=message, code=500)
