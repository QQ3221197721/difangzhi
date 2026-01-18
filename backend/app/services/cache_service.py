"""
Redis缓存服务
"""
import json
from typing import Any, Optional, Union
from datetime import timedelta
from loguru import logger
from app.core.database import get_redis
from app.core.config import settings


class CacheService:
    """Redis缓存服务"""
    
    def __init__(self):
        self.default_ttl = settings.REDIS_CACHE_TTL
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            redis = await get_redis()
            value = await redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"缓存读取失败: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """设置缓存"""
        try:
            redis = await get_redis()
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await redis.set(key, serialized, ex=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.error(f"缓存写入失败: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            redis = await get_redis()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"缓存删除失败: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配模式的缓存"""
        try:
            redis = await get_redis()
            keys = await redis.keys(pattern)
            if keys:
                return await redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"批量删除缓存失败: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            redis = await get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.error(f"缓存检查失败: {e}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """递增计数器"""
        try:
            redis = await get_redis()
            return await redis.incr(key, amount)
        except Exception as e:
            logger.error(f"计数器递增失败: {e}")
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """设置过期时间"""
        try:
            redis = await get_redis()
            return await redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"设置过期时间失败: {e}")
            return False


# 缓存键生成器
class CacheKeys:
    """缓存键管理"""
    
    @staticmethod
    def user_profile(user_id: str) -> str:
        return f"user:profile:{user_id}"
    
    @staticmethod
    def search_result(query_hash: str) -> str:
        return f"search:result:{query_hash}"
    
    @staticmethod
    def categories() -> str:
        return "data:categories"
    
    @staticmethod
    def record_detail(record_id: str) -> str:
        return f"record:detail:{record_id}"
    
    @staticmethod
    def statistics() -> str:
        return "data:statistics"
    
    @staticmethod
    def rate_limit(user_id: str, action: str) -> str:
        return f"rate_limit:{user_id}:{action}"
    
    @staticmethod
    def session(session_id: str) -> str:
        return f"session:{session_id}"


# 缓存装饰器
def cached(key_func, ttl: int = 3600):
    """缓存装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache = CacheService()
            cache_key = key_func(*args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            await cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# 全局缓存实例
cache_service = CacheService()
