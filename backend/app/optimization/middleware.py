"""
API优化中间件 - 限流、压缩、CORS、请求追踪、响应缓存
API Optimization Middleware - Rate Limiting, Compression, CORS, Request Tracing
"""

import asyncio
import gzip
import hashlib
import io
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ==================== 请求追踪中间件 ====================

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件 - 生成请求ID、记录耗时"""
    
    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        include_in_response: bool = True,
        log_requests: bool = True
    ):
        super().__init__(app)
        self.header_name = header_name
        self.include_in_response = include_in_response
        self.log_requests = log_requests
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        # 获取或生成请求ID
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())[:12]
        
        # 存储到请求状态
        request.state.request_id = request_id
        request.state.start_time = time.perf_counter()
        
        # 记录请求开始
        if self.log_requests:
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} "
                f"client={request.client.host if request.client else 'unknown'}"
            )
        
        try:
            response = await call_next(request)
            
            # 计算耗时
            duration_ms = (time.perf_counter() - request.state.start_time) * 1000
            
            # 添加响应头
            if self.include_in_response:
                response.headers[self.header_name] = request_id
                response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            # 记录请求结束
            if self.log_requests:
                logger.info(
                    f"[{request_id}] {response.status_code} "
                    f"duration={duration_ms:.2f}ms"
                )
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - request.state.start_time) * 1000
            logger.error(
                f"[{request_id}] ERROR {type(e).__name__}: {e} "
                f"duration={duration_ms:.2f}ms"
            )
            raise


# ==================== 限流中间件 ====================

class RateLimitAlgorithm(str, Enum):
    """限流算法"""
    FIXED_WINDOW = "fixed_window"      # 固定窗口
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口
    TOKEN_BUCKET = "token_bucket"      # 令牌桶
    LEAKY_BUCKET = "leaky_bucket"      # 漏桶


@dataclass
class RateLimitRule:
    """限流规则"""
    requests: int           # 请求数量
    window_seconds: int     # 时间窗口(秒)
    burst: Optional[int] = None  # 突发容量
    key_func: Optional[Callable[[Request], str]] = None  # 键函数


class RateLimiter:
    """限流器"""
    
    def __init__(
        self,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    ):
        self.algorithm = algorithm
        self._counters: Dict[str, Dict] = defaultdict(dict)
        self._lock = asyncio.Lock()
    
    async def is_allowed(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """检查是否允许请求"""
        async with self._lock:
            if self.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
                return self._fixed_window(key, rule)
            elif self.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                return self._sliding_window(key, rule)
            elif self.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                return self._token_bucket(key, rule)
            elif self.algorithm == RateLimitAlgorithm.LEAKY_BUCKET:
                return self._leaky_bucket(key, rule)
            return True, {}
    
    def _fixed_window(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """固定窗口算法"""
        now = time.time()
        window_start = int(now / rule.window_seconds) * rule.window_seconds
        
        counter = self._counters[key]
        
        if counter.get("window_start") != window_start:
            counter["window_start"] = window_start
            counter["count"] = 0
        
        remaining = rule.requests - counter["count"]
        
        if counter["count"] >= rule.requests:
            return False, {
                "limit": rule.requests,
                "remaining": 0,
                "reset": int(window_start + rule.window_seconds)
            }
        
        counter["count"] += 1
        return True, {
            "limit": rule.requests,
            "remaining": remaining - 1,
            "reset": int(window_start + rule.window_seconds)
        }
    
    def _sliding_window(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """滑动窗口算法"""
        now = time.time()
        window_start = now - rule.window_seconds
        
        counter = self._counters[key]
        
        # 清理过期记录
        if "timestamps" not in counter:
            counter["timestamps"] = []
        
        counter["timestamps"] = [
            ts for ts in counter["timestamps"]
            if ts > window_start
        ]
        
        remaining = rule.requests - len(counter["timestamps"])
        
        if len(counter["timestamps"]) >= rule.requests:
            oldest = min(counter["timestamps"])
            return False, {
                "limit": rule.requests,
                "remaining": 0,
                "reset": int(oldest + rule.window_seconds)
            }
        
        counter["timestamps"].append(now)
        return True, {
            "limit": rule.requests,
            "remaining": remaining - 1,
            "reset": int(now + rule.window_seconds)
        }
    
    def _token_bucket(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """令牌桶算法"""
        now = time.time()
        counter = self._counters[key]
        
        # 初始化
        if "tokens" not in counter:
            counter["tokens"] = float(rule.requests)
            counter["last_update"] = now
        
        # 补充令牌
        elapsed = now - counter["last_update"]
        refill_rate = rule.requests / rule.window_seconds
        counter["tokens"] = min(
            rule.burst or rule.requests,
            counter["tokens"] + elapsed * refill_rate
        )
        counter["last_update"] = now
        
        if counter["tokens"] < 1:
            return False, {
                "limit": rule.requests,
                "remaining": 0,
                "reset": int(now + (1 - counter["tokens"]) / refill_rate)
            }
        
        counter["tokens"] -= 1
        return True, {
            "limit": rule.requests,
            "remaining": int(counter["tokens"]),
            "reset": int(now + rule.window_seconds)
        }
    
    def _leaky_bucket(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """漏桶算法"""
        now = time.time()
        counter = self._counters[key]
        
        # 初始化
        if "water" not in counter:
            counter["water"] = 0.0
            counter["last_leak"] = now
        
        # 漏水
        elapsed = now - counter["last_leak"]
        leak_rate = rule.requests / rule.window_seconds
        counter["water"] = max(0, counter["water"] - elapsed * leak_rate)
        counter["last_leak"] = now
        
        capacity = rule.burst or rule.requests
        
        if counter["water"] >= capacity:
            return False, {
                "limit": rule.requests,
                "remaining": 0,
                "reset": int(now + counter["water"] / leak_rate)
            }
        
        counter["water"] += 1
        return True, {
            "limit": rule.requests,
            "remaining": int(capacity - counter["water"]),
            "reset": int(now + rule.window_seconds)
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        default_rule: RateLimitRule = None,
        path_rules: Dict[str, RateLimitRule] = None,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
        key_func: Callable[[Request], str] = None,
        exclude_paths: Set[str] = None
    ):
        super().__init__(app)
        self.default_rule = default_rule or RateLimitRule(100, 60)
        self.path_rules = path_rules or {}
        self.limiter = RateLimiter(algorithm)
        self.key_func = key_func or self._default_key_func
        self.exclude_paths = exclude_paths or {"/health", "/metrics"}
    
    def _default_key_func(self, request: Request) -> str:
        """默认键函数 - 基于IP"""
        client_ip = request.client.host if request.client else "unknown"
        return f"ratelimit:{client_ip}"
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        # 排除路径
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # 获取规则
        rule = self.path_rules.get(request.url.path, self.default_rule)
        
        # 获取键
        if rule.key_func:
            key = rule.key_func(request)
        else:
            key = self.key_func(request)
        
        # 检查限流
        allowed, info = await self.limiter.is_allowed(key, rule)
        
        if not allowed:
            return Response(
                content=json.dumps({
                    "error": "Too Many Requests",
                    "retry_after": info.get("reset", 60) - int(time.time())
                }),
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(info.get("limit", 0)),
                    "X-RateLimit-Remaining": str(info.get("remaining", 0)),
                    "X-RateLimit-Reset": str(info.get("reset", 0)),
                    "Retry-After": str(info.get("reset", 60) - int(time.time()))
                },
                media_type="application/json"
            )
        
        response = await call_next(request)
        
        # 添加限流头
        response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))
        
        return response


# ==================== 压缩中间件 ====================

class CompressionMiddleware(BaseHTTPMiddleware):
    """响应压缩中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_level: int = 6,
        include_content_types: Set[str] = None
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        self.include_content_types = include_content_types or {
            "application/json",
            "text/html",
            "text/plain",
            "text/css",
            "text/javascript",
            "application/javascript",
            "application/xml",
            "text/xml"
        }
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        # 检查客户端是否支持gzip
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        response = await call_next(request)
        
        # 检查是否应该压缩
        content_type = response.headers.get("Content-Type", "")
        content_type_base = content_type.split(";")[0].strip()
        
        if content_type_base not in self.include_content_types:
            return response
        
        # 对于StreamingResponse需要特殊处理
        if isinstance(response, StreamingResponse):
            return response
        
        # 获取响应体
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # 检查大小
        if len(body) < self.minimum_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        # 压缩
        compressed = gzip.compress(body, compresslevel=self.compression_level)
        
        # 只有压缩后更小才使用
        if len(compressed) >= len(body):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        headers = dict(response.headers)
        headers["Content-Encoding"] = "gzip"
        headers["Content-Length"] = str(len(compressed))
        headers["Vary"] = "Accept-Encoding"
        
        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type
        )


# ==================== CORS中间件增强 ====================

@dataclass
class CORSConfig:
    """CORS配置"""
    allow_origins: List[str] = field(default_factory=lambda: ["*"])
    allow_methods: List[str] = field(default_factory=lambda: ["*"])
    allow_headers: List[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = False
    expose_headers: List[str] = field(default_factory=list)
    max_age: int = 600
    allow_origin_regex: Optional[str] = None


class EnhancedCORSMiddleware:
    """增强CORS中间件 - 支持动态配置"""
    
    def __init__(
        self,
        app: ASGIApp,
        config: CORSConfig = None,
        config_provider: Callable[[], CORSConfig] = None
    ):
        self.app = app
        self._static_config = config or CORSConfig()
        self._config_provider = config_provider
    
    @property
    def config(self) -> CORSConfig:
        """获取配置"""
        if self._config_provider:
            return self._config_provider()
        return self._static_config
    
    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        origin = request.headers.get("origin")
        
        # 预检请求
        if request.method == "OPTIONS":
            response = self._preflight_response(origin)
            await response(scope, receive, send)
            return
        
        # 普通请求
        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                cors_headers = self._get_cors_headers(origin)
                
                for key, value in cors_headers.items():
                    headers[key.encode()] = value.encode()
                
                message["headers"] = list(headers.items())
            
            await send(message)
        
        await self.app(scope, receive, send_with_cors)
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """检查来源是否允许"""
        if not origin:
            return False
        
        config = self.config
        
        if "*" in config.allow_origins:
            return True
        
        if origin in config.allow_origins:
            return True
        
        if config.allow_origin_regex:
            import re
            if re.match(config.allow_origin_regex, origin):
                return True
        
        return False
    
    def _get_cors_headers(self, origin: str) -> Dict[str, str]:
        """获取CORS响应头"""
        config = self.config
        headers = {}
        
        if self._is_origin_allowed(origin):
            if "*" in config.allow_origins and not config.allow_credentials:
                headers["Access-Control-Allow-Origin"] = "*"
            else:
                headers["Access-Control-Allow-Origin"] = origin
        
        if config.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"
        
        if config.expose_headers:
            headers["Access-Control-Expose-Headers"] = ", ".join(config.expose_headers)
        
        return headers
    
    def _preflight_response(self, origin: str) -> Response:
        """预检响应"""
        config = self.config
        headers = self._get_cors_headers(origin)
        
        if self._is_origin_allowed(origin):
            if "*" in config.allow_methods:
                headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            else:
                headers["Access-Control-Allow-Methods"] = ", ".join(config.allow_methods)
            
            if "*" in config.allow_headers:
                headers["Access-Control-Allow-Headers"] = "*"
            else:
                headers["Access-Control-Allow-Headers"] = ", ".join(config.allow_headers)
            
            headers["Access-Control-Max-Age"] = str(config.max_age)
        
        return Response(
            content="",
            status_code=204,
            headers=headers
        )


# ==================== 响应缓存中间件 ====================

class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """响应缓存中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        cache_ttl: int = 60,
        cacheable_methods: Set[str] = None,
        cacheable_status_codes: Set[int] = None,
        cache_key_func: Callable[[Request], str] = None,
        exclude_paths: Set[str] = None,
        max_cache_size: int = 1000
    ):
        super().__init__(app)
        self.cache_ttl = cache_ttl
        self.cacheable_methods = cacheable_methods or {"GET", "HEAD"}
        self.cacheable_status_codes = cacheable_status_codes or {200, 301, 304}
        self.cache_key_func = cache_key_func or self._default_cache_key
        self.exclude_paths = exclude_paths or set()
        
        self._cache: Dict[str, Tuple[Response, float]] = {}
        self._max_cache_size = max_cache_size
        self._lock = asyncio.Lock()
    
    def _default_cache_key(self, request: Request) -> str:
        """默认缓存键"""
        key_parts = [
            request.method,
            str(request.url),
            request.headers.get("Accept", ""),
            request.headers.get("Accept-Encoding", "")
        ]
        return hashlib.md5(":".join(key_parts).encode()).hexdigest()
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        # 检查是否可缓存
        if request.method not in self.cacheable_methods:
            return await call_next(request)
        
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # 检查缓存控制头
        cache_control = request.headers.get("Cache-Control", "")
        if "no-cache" in cache_control or "no-store" in cache_control:
            return await call_next(request)
        
        # 生成缓存键
        cache_key = self.cache_key_func(request)
        
        # 尝试从缓存获取
        cached = await self._get_from_cache(cache_key)
        if cached:
            cached.headers["X-Cache"] = "HIT"
            return cached
        
        # 执行请求
        response = await call_next(request)
        
        # 检查是否应该缓存
        if response.status_code in self.cacheable_status_codes:
            response_cache_control = response.headers.get("Cache-Control", "")
            if "no-store" not in response_cache_control:
                await self._store_in_cache(cache_key, response)
        
        response.headers["X-Cache"] = "MISS"
        return response
    
    async def _get_from_cache(self, key: str) -> Optional[Response]:
        """从缓存获取"""
        async with self._lock:
            if key in self._cache:
                response, expires_at = self._cache[key]
                if time.time() < expires_at:
                    return response
                del self._cache[key]
        return None
    
    async def _store_in_cache(self, key: str, response: Response):
        """存储到缓存"""
        async with self._lock:
            # 淘汰旧条目
            if len(self._cache) >= self._max_cache_size:
                # 删除最早的
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            # 读取响应体
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # 创建可缓存的响应
            cached_response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
            self._cache[key] = (cached_response, time.time() + self.cache_ttl)


# ==================== 请求验证中间件 ====================

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """请求验证中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        max_content_length: int = 10 * 1024 * 1024,  # 10MB
        allowed_content_types: Set[str] = None,
        required_headers: Dict[str, str] = None
    ):
        super().__init__(app)
        self.max_content_length = max_content_length
        self.allowed_content_types = allowed_content_types or {
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data"
        }
        self.required_headers = required_headers or {}
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        # 检查Content-Length
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.max_content_length:
                    return Response(
                        content=json.dumps({
                            "error": "Request Entity Too Large",
                            "max_size": self.max_content_length
                        }),
                        status_code=413,
                        media_type="application/json"
                    )
            except ValueError:
                pass
        
        # 检查Content-Type
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("Content-Type", "")
            content_type_base = content_type.split(";")[0].strip()
            
            if content_type_base and content_type_base not in self.allowed_content_types:
                return Response(
                    content=json.dumps({
                        "error": "Unsupported Media Type",
                        "allowed": list(self.allowed_content_types)
                    }),
                    status_code=415,
                    media_type="application/json"
                )
        
        # 检查必需头
        for header, expected in self.required_headers.items():
            actual = request.headers.get(header)
            if actual != expected:
                return Response(
                    content=json.dumps({
                        "error": f"Missing or invalid header: {header}"
                    }),
                    status_code=400,
                    media_type="application/json"
                )
        
        return await call_next(request)


# ==================== 超时中间件 ====================

class TimeoutMiddleware(BaseHTTPMiddleware):
    """请求超时中间件"""
    
    def __init__(
        self,
        app: ASGIApp,
        timeout_seconds: float = 30.0,
        path_timeouts: Dict[str, float] = None
    ):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
        self.path_timeouts = path_timeouts or {}
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        timeout = self.path_timeouts.get(
            request.url.path,
            self.timeout_seconds
        )
        
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return Response(
                content=json.dumps({
                    "error": "Request Timeout",
                    "timeout_seconds": timeout
                }),
                status_code=504,
                media_type="application/json"
            )


# ==================== 中间件管理器 ====================

class MiddlewareManager:
    """中间件管理器 - 统一配置和管理中间件"""
    
    def __init__(self, app: ASGIApp):
        self.app = app
        self._middlewares: List[Tuple[type, Dict]] = []
    
    def add_request_tracing(
        self,
        header_name: str = "X-Request-ID",
        log_requests: bool = True
    ) -> "MiddlewareManager":
        """添加请求追踪"""
        self._middlewares.append((
            RequestTracingMiddleware,
            {"header_name": header_name, "log_requests": log_requests}
        ))
        return self
    
    def add_rate_limiting(
        self,
        requests_per_minute: int = 100,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    ) -> "MiddlewareManager":
        """添加限流"""
        self._middlewares.append((
            RateLimitMiddleware,
            {
                "default_rule": RateLimitRule(requests_per_minute, 60),
                "algorithm": algorithm
            }
        ))
        return self
    
    def add_compression(
        self,
        minimum_size: int = 500,
        compression_level: int = 6
    ) -> "MiddlewareManager":
        """添加压缩"""
        self._middlewares.append((
            CompressionMiddleware,
            {"minimum_size": minimum_size, "compression_level": compression_level}
        ))
        return self
    
    def add_cors(self, config: CORSConfig = None) -> "MiddlewareManager":
        """添加CORS"""
        self._middlewares.append((
            EnhancedCORSMiddleware,
            {"config": config or CORSConfig()}
        ))
        return self
    
    def add_response_cache(
        self,
        cache_ttl: int = 60,
        max_cache_size: int = 1000
    ) -> "MiddlewareManager":
        """添加响应缓存"""
        self._middlewares.append((
            ResponseCacheMiddleware,
            {"cache_ttl": cache_ttl, "max_cache_size": max_cache_size}
        ))
        return self
    
    def add_timeout(
        self,
        timeout_seconds: float = 30.0
    ) -> "MiddlewareManager":
        """添加超时"""
        self._middlewares.append((
            TimeoutMiddleware,
            {"timeout_seconds": timeout_seconds}
        ))
        return self
    
    def add_validation(
        self,
        max_content_length: int = 10 * 1024 * 1024
    ) -> "MiddlewareManager":
        """添加请求验证"""
        self._middlewares.append((
            RequestValidationMiddleware,
            {"max_content_length": max_content_length}
        ))
        return self
    
    def build(self) -> ASGIApp:
        """构建中间件链"""
        app = self.app
        
        for middleware_class, kwargs in reversed(self._middlewares):
            app = middleware_class(app, **kwargs)
        
        return app


# ==================== 导出 ====================

__all__ = [
    # 请求追踪
    "RequestTracingMiddleware",
    # 限流
    "RateLimitAlgorithm",
    "RateLimitRule",
    "RateLimiter",
    "RateLimitMiddleware",
    # 压缩
    "CompressionMiddleware",
    # CORS
    "CORSConfig",
    "EnhancedCORSMiddleware",
    # 响应缓存
    "ResponseCacheMiddleware",
    # 请求验证
    "RequestValidationMiddleware",
    # 超时
    "TimeoutMiddleware",
    # 管理器
    "MiddlewareManager",
]
