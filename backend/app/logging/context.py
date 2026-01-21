# 地方志数据智能管理系统 - 日志上下文
"""请求上下文和追踪"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps
import structlog

# 上下文变量
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_span_id: ContextVar[str] = ContextVar("span_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


@dataclass
class LogContext:
    """日志上下文"""
    trace_id: str = ""
    span_id: str = ""
    request_id: str = ""
    user_id: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())
        if not self.span_id:
            self.span_id = str(uuid.uuid4())[:8]
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
    
    def bind(self):
        """绑定到当前上下文"""
        _trace_id.set(self.trace_id)
        _span_id.set(self.span_id)
        _request_id.set(self.request_id)
        if self.user_id:
            _user_id.set(self.user_id)
        
        # 绑定到structlog
        structlog.contextvars.bind_contextvars(
            trace_id=self.trace_id,
            span_id=self.span_id,
            request_id=self.request_id,
            user_id=self.user_id
        )
    
    def unbind(self):
        """清除上下文"""
        structlog.contextvars.unbind_contextvars(
            "trace_id", "span_id", "request_id", "user_id"
        )
    
    @classmethod
    def current(cls) -> "LogContext":
        """获取当前上下文"""
        return cls(
            trace_id=_trace_id.get(),
            span_id=_span_id.get(),
            request_id=_request_id.get(),
            user_id=_user_id.get()
        )


@dataclass
class RequestContext:
    """HTTP请求上下文"""
    trace_id: str
    request_id: str
    method: str
    path: str
    client_ip: str
    user_agent: str
    user_id: Optional[int] = None
    start_time: datetime = None
    
    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.now()
    
    def to_log_context(self) -> LogContext:
        """转换为日志上下文"""
        return LogContext(
            trace_id=self.trace_id,
            request_id=self.request_id,
            user_id=self.user_id,
            extra={
                "method": self.method,
                "path": self.path,
                "client_ip": self.client_ip
            }
        )
    
    @classmethod
    def from_request(cls, request) -> "RequestContext":
        """从FastAPI请求创建"""
        # 尝试从请求头获取追踪ID
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        return cls(
            trace_id=trace_id,
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", "unknown")
        )


def trace_context(func):
    """追踪上下文装饰器"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        ctx = LogContext()
        ctx.bind()
        try:
            return await func(*args, **kwargs)
        finally:
            ctx.unbind()
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        ctx = LogContext()
        ctx.bind()
        try:
            return func(*args, **kwargs)
        finally:
            ctx.unbind()
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class SpanContext:
    """Span上下文管理器"""
    
    def __init__(self, name: str, parent_span_id: str = None):
        self.name = name
        self.span_id = str(uuid.uuid4())[:8]
        self.parent_span_id = parent_span_id or _span_id.get()
        self.start_time = None
        self.logger = structlog.get_logger()
    
    def __enter__(self):
        self.start_time = datetime.now()
        _span_id.set(self.span_id)
        structlog.contextvars.bind_contextvars(
            span_id=self.span_id,
            parent_span_id=self.parent_span_id
        )
        self.logger.debug(f"Span开始: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds() * 1000
        if exc_type:
            self.logger.error(
                f"Span异常: {self.name}",
                duration_ms=duration,
                error=str(exc_val)
            )
        else:
            self.logger.debug(
                f"Span完成: {self.name}",
                duration_ms=duration
            )
        _span_id.set(self.parent_span_id)
        return False
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# FastAPI中间件
class LoggingMiddleware:
    """日志中间件"""
    
    def __init__(self, app):
        self.app = app
        self.logger = structlog.get_logger()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        from starlette.requests import Request
        request = Request(scope, receive)
        ctx = RequestContext.from_request(request)
        log_ctx = ctx.to_log_context()
        log_ctx.bind()
        
        # 记录请求开始
        self.logger.info(
            "请求开始",
            method=ctx.method,
            path=ctx.path,
            client_ip=ctx.client_ip
        )
        
        # 捕获响应状态码
        status_code = 500
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            self.logger.error("请求异常", error=str(e))
            raise
        finally:
            duration = (datetime.now() - ctx.start_time).total_seconds() * 1000
            self.logger.info(
                "请求完成",
                status_code=status_code,
                duration_ms=duration
            )
            log_ctx.unbind()
