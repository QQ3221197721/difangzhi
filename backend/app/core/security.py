"""
地方志系统 - 安全配置模块
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib

from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
import redis.asyncio as redis

from app.core.config import settings


# Token 黑名单 Redis 客户端
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


class TokenBlacklist:
    """Token 黑名单管理"""
    
    PREFIX = "token_blacklist:"
    
    @classmethod
    async def add(cls, token: str, expires_in: int = 86400) -> None:
        """将 token 加入黑名单"""
        client = await get_redis_client()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await client.setex(f"{cls.PREFIX}{token_hash}", expires_in, "1")
    
    @classmethod
    async def is_blacklisted(cls, token: str) -> bool:
        """检查 token 是否在黑名单中"""
        client = await get_redis_client()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return await client.exists(f"{cls.PREFIX}{token_hash}") > 0


class RateLimiter:
    """请求限流器"""
    
    PREFIX = "rate_limit:"
    
    @classmethod
    async def check(cls, key: str, limit: int = 100, window: int = 60) -> bool:
        """
        检查是否超过限流
        Args:
            key: 限流 key（如用户 ID 或 IP）
            limit: 时间窗口内最大请求数
            window: 时间窗口（秒）
        Returns:
            True 表示允许请求，False 表示超过限流
        """
        client = await get_redis_client()
        full_key = f"{cls.PREFIX}{key}"
        
        current = await client.get(full_key)
        if current is None:
            await client.setex(full_key, window, 1)
            return True
        
        if int(current) >= limit:
            return False
        
        await client.incr(full_key)
        return True
    
    @classmethod
    async def get_remaining(cls, key: str, limit: int = 100) -> int:
        """获取剩余请求次数"""
        client = await get_redis_client()
        full_key = f"{cls.PREFIX}{key}"
        current = await client.get(full_key)
        if current is None:
            return limit
        return max(0, limit - int(current))


class LoginAttemptTracker:
    """登录尝试跟踪器（防暴力破解）"""
    
    PREFIX = "login_attempt:"
    MAX_ATTEMPTS = 5
    LOCKOUT_TIME = 900  # 15分钟
    
    @classmethod
    async def record_attempt(cls, username: str, success: bool) -> None:
        """记录登录尝试"""
        client = await get_redis_client()
        key = f"{cls.PREFIX}{username}"
        
        if success:
            await client.delete(key)
        else:
            attempts = await client.incr(key)
            if attempts == 1:
                await client.expire(key, cls.LOCKOUT_TIME)
    
    @classmethod
    async def is_locked(cls, username: str) -> bool:
        """检查账户是否被锁定"""
        client = await get_redis_client()
        key = f"{cls.PREFIX}{username}"
        attempts = await client.get(key)
        if attempts and int(attempts) >= cls.MAX_ATTEMPTS:
            return True
        return False
    
    @classmethod
    async def get_remaining_attempts(cls, username: str) -> int:
        """获取剩余尝试次数"""
        client = await get_redis_client()
        key = f"{cls.PREFIX}{username}"
        attempts = await client.get(key)
        if attempts is None:
            return cls.MAX_ATTEMPTS
        return max(0, cls.MAX_ATTEMPTS - int(attempts))


def generate_csrf_token() -> str:
    """生成 CSRF Token"""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, session_token: str) -> bool:
    """验证 CSRF Token"""
    return secrets.compare_digest(token, session_token)


class SecurityHeaders:
    """安全响应头"""
    
    @staticmethod
    def get_headers() -> dict:
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """清理用户输入"""
    if not text:
        return ""
    
    # 截断过长文本
    text = text[:max_length]
    
    # 移除潜在危险字符
    dangerous_chars = ['<script>', '</script>', 'javascript:', 'onerror=', 'onclick=']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text.strip()


def validate_file_extension(filename: str, allowed: list = None) -> bool:
    """验证文件扩展名"""
    if allowed is None:
        allowed = settings.ALLOWED_EXTENSIONS
    
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in allowed


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"
