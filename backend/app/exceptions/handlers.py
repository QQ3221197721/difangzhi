# 地方志数据智能管理系统 - 异常处理器
"""FastAPI异常处理器注册"""

import traceback
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import structlog

from .exceptions import BaseAPIException

logger = structlog.get_logger()


async def api_exception_handler(
    request: Request,
    exc: BaseAPIException
) -> JSONResponse:
    """
    自定义API异常处理器
    
    Args:
        request: 请求对象
        exc: API异常
        
    Returns:
        JSON响应
    """
    logger.warning(
        "api_exception",
        path=request.url.path,
        method=request.method,
        code=exc.code,
        message=exc.message,
    )
    
    headers = {}
    if hasattr(exc, 'retry_after') and exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers=headers or None
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    请求验证异常处理器
    
    Args:
        request: 请求对象
        exc: 验证异常
        
    Returns:
        JSON响应
    """
    errors = []
    
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        errors.append({
            "field": field,
            "message": error.get("msg", "验证失败"),
            "type": error.get("type", "")
        })
    
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=errors
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": None,
            "errors": errors
        }
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    通用异常处理器
    
    Args:
        request: 请求对象
        exc: 异常
        
    Returns:
        JSON响应
    """
    # 记录详细错误日志
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        traceback=traceback.format_exc()
    )
    
    # 生产环境不暴露详细错误
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None
        }
    )


async def http_exception_handler(
    request: Request,
    exc
) -> JSONResponse:
    """
    HTTP异常处理器
    
    Args:
        request: 请求对象
        exc: HTTP异常
        
    Returns:
        JSON响应
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail or "请求错误",
            "data": None
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册所有异常处理器
    
    Args:
        app: FastAPI应用实例
    """
    from fastapi.exceptions import HTTPException
    
    # 注册自定义API异常处理器
    app.add_exception_handler(BaseAPIException, api_exception_handler)
    
    # 注册验证异常处理器
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    
    # 注册HTTP异常处理器
    app.add_exception_handler(HTTPException, http_exception_handler)
    
    # 注册通用异常处理器
    app.add_exception_handler(Exception, generic_exception_handler)


class ExceptionMiddleware:
    """异常中间件（备选方案）"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        try:
            await self.app(scope, receive, send)
        except BaseAPIException as exc:
            response = JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )
            await response(scope, receive, send)
        except Exception as exc:
            logger.error("middleware_exception", error=str(exc))
            response = JSONResponse(
                status_code=500,
                content={
                    "code": 500,
                    "message": "服务器内部错误",
                    "data": None
                }
            )
            await response(scope, receive, send)
