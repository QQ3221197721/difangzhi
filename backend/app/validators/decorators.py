# 地方志数据智能管理系统 - 验证装饰器
"""请求验证和限流装饰器"""

import functools
import time
from typing import Any, Callable, Dict, List, Optional, Type
from collections import defaultdict

from fastapi import HTTPException, Request
from pydantic import BaseModel

from app.exceptions import ValidationException, RateLimitException


def validate_request(
    schema: Type[BaseModel],
    location: str = "body"
):
    """
    请求数据验证装饰器
    
    Args:
        schema: Pydantic模型类
        location: 数据位置 (body/query/path)
        
    Example:
        @validate_request(CreateUserSchema)
        async def create_user(request: Request):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request is None:
                return await func(*args, **kwargs)
            
            try:
                if location == "body":
                    data = await request.json()
                elif location == "query":
                    data = dict(request.query_params)
                else:
                    data = request.path_params
                
                validated = schema(**data)
                kwargs['validated_data'] = validated
                
            except Exception as e:
                raise ValidationException(
                    message="请求数据验证失败",
                    errors=[{"field": "request", "message": str(e)}]
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class RateLimiter:
    """
    请求限流器
    
    使用滑动窗口算法
    """
    
    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, Optional[int]]:
        """
        检查是否允许请求
        
        Args:
            key: 限流键
            max_requests: 窗口内最大请求数
            window_seconds: 窗口大小（秒）
            
        Returns:
            (是否允许, 重试等待秒数)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # 清理过期记录
        self._requests[key] = [
            t for t in self._requests[key] 
            if t > window_start
        ]
        
        if len(self._requests[key]) >= max_requests:
            # 计算需要等待的时间
            oldest = min(self._requests[key])
            retry_after = int(oldest + window_seconds - now) + 1
            return False, retry_after
        
        self._requests[key].append(now)
        return True, None
    
    def reset(self, key: str):
        """重置指定键的计数"""
        self._requests.pop(key, None)


# 全局限流器实例
_rate_limiter = RateLimiter()


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_func: Optional[Callable[[Request], str]] = None
):
    """
    请求限流装饰器
    
    Args:
        max_requests: 窗口内最大请求数
        window_seconds: 窗口大小（秒）
        key_func: 自定义限流键函数
        
    Example:
        @rate_limit(max_requests=10, window_seconds=60)
        async def api_endpoint(request: Request):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request is None:
                return await func(*args, **kwargs)
            
            # 生成限流键
            if key_func:
                key = key_func(request)
            else:
                # 默认使用IP + 路径作为限流键
                client_ip = request.client.host if request.client else "unknown"
                key = f"{client_ip}:{request.url.path}"
            
            allowed, retry_after = _rate_limiter.is_allowed(
                key, max_requests, window_seconds
            )
            
            if not allowed:
                raise RateLimitException(retry_after=retry_after)
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def validate_content_type(allowed_types: List[str]):
    """
    Content-Type验证装饰器
    
    Args:
        allowed_types: 允许的Content-Type列表
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request is None:
                return await func(*args, **kwargs)
            
            content_type = request.headers.get("content-type", "")
            
            if not any(ct in content_type for ct in allowed_types):
                raise HTTPException(
                    status_code=415,
                    detail=f"不支持的Content-Type: {content_type}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_fields(*fields: str):
    """
    必填字段验证装饰器
    
    Args:
        fields: 必填字段名列表
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request is None:
                return await func(*args, **kwargs)
            
            try:
                data = await request.json()
            except:
                data = {}
            
            missing = [f for f in fields if f not in data or data[f] is None]
            
            if missing:
                raise ValidationException(
                    message=f"缺少必填字段: {', '.join(missing)}",
                    errors=[
                        {"field": f, "message": "此字段为必填项"} 
                        for f in missing
                    ]
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def sanitize_input(fields: Optional[List[str]] = None):
    """
    输入清洗装饰器
    
    Args:
        fields: 需要清洗的字段列表，None表示全部字符串字段
    """
    import html
    
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get('request')
            if not request:
                return await func(*args, **kwargs)
            
            try:
                data = await request.json()
                
                def sanitize(obj):
                    if isinstance(obj, str):
                        # 移除HTML标签和转义
                        return html.escape(obj.strip())
                    elif isinstance(obj, dict):
                        return {
                            k: sanitize(v) if fields is None or k in fields else v
                            for k, v in obj.items()
                        }
                    elif isinstance(obj, list):
                        return [sanitize(item) for item in obj]
                    return obj
                
                kwargs['sanitized_data'] = sanitize(data)
                
            except:
                pass
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
