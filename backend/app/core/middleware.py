"""
安全中间件 - 请求限流、XSS防护、SQL注入防护
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from typing import Dict, Optional
import re
import json
from loguru import logger
from app.core.config import settings


class SecurityMiddleware(BaseHTTPMiddleware):
    """综合安全中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limit_store: Dict[str, list] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        
        # XSS危险模式
        self.xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>',
        ]
        
        # SQL注入模式
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)",
            r"(--)|(;)",
            r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)",
            r"'.*'",
        ]
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        # 检查IP是否被封禁
        if self._is_ip_blocked(client_ip):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "IP已被临时封禁，请稍后重试"}
            )
        
        # 速率限制检查
        if not await self._check_rate_limit(client_ip, request.url.path):
            self._block_ip(client_ip, minutes=5)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "请求过于频繁，请稍后重试"}
            )
        
        # 请求内容安全检查
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    body_str = body.decode('utf-8', errors='ignore')
                    
                    # XSS检查
                    if self._check_xss(body_str):
                        logger.warning(f"XSS攻击检测: IP={client_ip}, Path={request.url.path}")
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={"detail": "请求包含不安全内容"}
                        )
                    
                    # SQL注入检查（仅对非JSON请求）
                    content_type = request.headers.get("content-type", "")
                    if "json" not in content_type and self._check_sql_injection(body_str):
                        logger.warning(f"SQL注入检测: IP={client_ip}, Path={request.url.path}")
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={"detail": "请求包含不安全内容"}
                        )
            except Exception as e:
                logger.error(f"安全检查失败: {e}")
        
        # 添加安全响应头
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """获取真实客户端IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, ip: str, path: str) -> bool:
        """检查速率限制"""
        key = f"{ip}:{path}"
        now = datetime.utcnow()
        window = timedelta(minutes=1)
        
        if key not in self.rate_limit_store:
            self.rate_limit_store[key] = []
        
        # 清理过期记录
        self.rate_limit_store[key] = [
            t for t in self.rate_limit_store[key] 
            if now - t < window
        ]
        
        # 检查限制（每分钟100次）
        if len(self.rate_limit_store[key]) >= 100:
            return False
        
        self.rate_limit_store[key].append(now)
        return True
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """检查IP是否被封禁"""
        if ip in self.blocked_ips:
            if datetime.utcnow() < self.blocked_ips[ip]:
                return True
            del self.blocked_ips[ip]
        return False
    
    def _block_ip(self, ip: str, minutes: int = 5):
        """封禁IP"""
        self.blocked_ips[ip] = datetime.utcnow() + timedelta(minutes=minutes)
        logger.warning(f"IP被封禁: {ip}, 时长: {minutes}分钟")
    
    def _check_xss(self, content: str) -> bool:
        """检查XSS攻击"""
        for pattern in self.xss_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def _check_sql_injection(self, content: str) -> bool:
        """检查SQL注入（简化版，实际应使用参数化查询）"""
        for pattern in self.sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                # 排除正常业务场景
                if len(content) < 500:  # 长内容可能是正常文本
                    return True
        return False


class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()
        
        # 获取请求信息
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        user_agent = request.headers.get("User-Agent", "")
        
        # 执行请求
        response = await call_next(request)
        
        # 计算耗时
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # 记录关键操作
        if request.method in ["POST", "PUT", "DELETE"]:
            logger.info(
                f"AUDIT | {request.method} {request.url.path} | "
                f"IP: {client_ip} | Status: {response.status_code} | "
                f"Duration: {duration:.2f}ms"
            )
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """请求验证中间件"""
    
    # 敏感路径（需要额外验证）
    SENSITIVE_PATHS = [
        "/api/v1/auth/verify-identity",
        "/api/v1/upload/",
        "/api/v1/analysis/",
    ]
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 检查Content-Type
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            
            # 文件上传除外
            if "multipart/form-data" not in content_type:
                if path.startswith("/api/") and "json" not in content_type:
                    # 允许空body的请求
                    content_length = request.headers.get("content-length", "0")
                    if int(content_length) > 0:
                        return JSONResponse(
                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            content={"detail": "Content-Type必须为application/json"}
                        )
        
        # 请求大小限制（100MB）
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 100 * 1024 * 1024:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "请求体过大"}
            )
        
        return await call_next(request)
