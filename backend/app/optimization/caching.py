"""
高级缓存模块 - Redis集群、缓存预热、防穿透、多级缓存
Advanced Caching Module - Redis Cluster, Cache Warming, Anti-Penetration
"""

import asyncio
import functools
import hashlib
import json
import pickle
import random
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Callable, Dict, Generic, List, Optional, 
    Set, Tuple, TypeVar, Union
)
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ==================== 缓存策略 ====================

class EvictionPolicy(str, Enum):
    """淘汰策略"""
    LRU = "lru"           # 最近最少使用
    LFU = "lfu"           # 最不经常使用
    FIFO = "fifo"         # 先进先出
    TTL = "ttl"           # 按过期时间
    RANDOM = "random"     # 随机淘汰


class CacheLevel(str, Enum):
    """缓存层级"""
    L1_MEMORY = "l1_memory"     # 内存缓存(最快)
    L2_LOCAL = "l2_local"       # 本地缓存
    L3_DISTRIBUTED = "l3_distributed"  # 分布式缓存


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    key: str
    value: T
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0
    tags: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size: int = 0
    memory_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# ==================== 缓存后端接口 ====================

class CacheBackend(ABC, Generic[T]):
    """缓存后端抽象基类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[T]:
        """获取缓存"""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None
    ) -> bool:
        """设置缓存"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        pass
    
    @abstractmethod
    async def clear(self) -> int:
        """清空缓存"""
        pass
    
    @abstractmethod
    def get_stats(self) -> CacheStats:
        """获取统计"""
        pass


# ==================== 内存缓存 ====================

class MemoryCache(CacheBackend[T]):
    """内存缓存 - LRU/LFU/FIFO策略"""
    
    def __init__(
        self,
        max_size: int = 10000,
        max_memory_mb: int = 512,
        default_ttl: int = 3600,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    ):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.eviction_policy = eviction_policy
        
        self._cache: Dict[str, CacheEntry[T]] = OrderedDict()
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        """获取缓存"""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                return None
            
            entry.touch()
            
            # LRU: 移到末尾
            if self.eviction_policy == EvictionPolicy.LRU:
                self._cache.move_to_end(key)
            
            self._stats.hits += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None
    ) -> bool:
        """设置缓存"""
        async with self._lock:
            # 计算大小
            size = self._estimate_size(value)
            
            # 淘汰以腾出空间
            await self._evict_if_needed(size)
            
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl
            elif self.default_ttl:
                expires_at = time.time() + self.default_ttl
            
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                size_bytes=size,
                tags=tags or set()
            )
            
            # 如果已存在，先减去旧大小
            if key in self._cache:
                self._stats.memory_bytes -= self._cache[key].size_bytes
            
            self._cache[key] = entry
            self._stats.sets += 1
            self._stats.size = len(self._cache)
            self._stats.memory_bytes += size
            
            return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._stats.deletes += 1
                self._stats.size = len(self._cache)
                self._stats.memory_bytes -= entry.size_bytes
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        entry = self._cache.get(key)
        if entry is None:
            return False
        if entry.is_expired():
            await self.delete(key)
            return False
        return True
    
    async def clear(self) -> int:
        """清空缓存"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.size = 0
            self._stats.memory_bytes = 0
            return count
    
    async def delete_by_tags(self, tags: Set[str]) -> int:
        """按标签删除"""
        async with self._lock:
            to_delete = [
                key for key, entry in self._cache.items()
                if entry.tags & tags
            ]
            for key in to_delete:
                entry = self._cache.pop(key)
                self._stats.memory_bytes -= entry.size_bytes
            
            self._stats.size = len(self._cache)
            self._stats.deletes += len(to_delete)
            return len(to_delete)
    
    async def _evict_if_needed(self, needed_bytes: int = 0):
        """按策略淘汰"""
        # 检查数量限制
        while len(self._cache) >= self.max_size:
            await self._evict_one()
        
        # 检查内存限制
        while self._stats.memory_bytes + needed_bytes > self.max_memory_bytes:
            if not self._cache:
                break
            await self._evict_one()
    
    async def _evict_one(self):
        """淘汰一个条目"""
        if not self._cache:
            return
        
        key_to_evict = None
        
        if self.eviction_policy == EvictionPolicy.LRU:
            # 最近最少使用(OrderedDict头部)
            key_to_evict = next(iter(self._cache))
        
        elif self.eviction_policy == EvictionPolicy.LFU:
            # 最不经常使用
            key_to_evict = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
        
        elif self.eviction_policy == EvictionPolicy.FIFO:
            # 先进先出
            key_to_evict = next(iter(self._cache))
        
        elif self.eviction_policy == EvictionPolicy.TTL:
            # 最早过期
            key_to_evict = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].expires_at or float('inf')
            )
        
        elif self.eviction_policy == EvictionPolicy.RANDOM:
            # 随机
            key_to_evict = random.choice(list(self._cache.keys()))
        
        if key_to_evict:
            entry = self._cache.pop(key_to_evict)
            self._stats.evictions += 1
            self._stats.size = len(self._cache)
            self._stats.memory_bytes -= entry.size_bytes
    
    def _estimate_size(self, value: Any) -> int:
        """估算对象大小"""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return 1024  # 默认1KB
    
    def get_stats(self) -> CacheStats:
        """获取统计"""
        return self._stats


# ==================== Redis缓存 ====================

class RedisCache(CacheBackend[T]):
    """Redis分布式缓存"""
    
    def __init__(
        self,
        redis_client: Any,  # redis.asyncio.Redis
        prefix: str = "cache:",
        default_ttl: int = 3600,
        serializer: str = "json"  # json/pickle
    ):
        self.redis = redis_client
        self.prefix = prefix
        self.default_ttl = default_ttl
        self.serializer = serializer
        self._stats = CacheStats()
    
    def _make_key(self, key: str) -> str:
        """生成Redis键"""
        return f"{self.prefix}{key}"
    
    def _serialize(self, value: T) -> bytes:
        """序列化"""
        if self.serializer == "json":
            return json.dumps(value, ensure_ascii=False).encode()
        return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> T:
        """反序列化"""
        if self.serializer == "json":
            return json.loads(data.decode())
        return pickle.loads(data)
    
    async def get(self, key: str) -> Optional[T]:
        """获取缓存"""
        try:
            data = await self.redis.get(self._make_key(key))
            if data is None:
                self._stats.misses += 1
                return None
            
            self._stats.hits += 1
            return self._deserialize(data)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats.misses += 1
            return None
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None
    ) -> bool:
        """设置缓存"""
        try:
            data = self._serialize(value)
            ex = ttl or self.default_ttl
            
            await self.redis.set(self._make_key(key), data, ex=ex)
            
            # 存储标签关系
            if tags:
                for tag in tags:
                    await self.redis.sadd(f"{self.prefix}tag:{tag}", key)
                    await self.redis.expire(f"{self.prefix}tag:{tag}", ex)
            
            self._stats.sets += 1
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            result = await self.redis.delete(self._make_key(key))
            if result:
                self._stats.deletes += 1
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        try:
            return await self.redis.exists(self._make_key(key)) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> int:
        """清空缓存(按前缀)"""
        try:
            keys = []
            async for key in self.redis.scan_iter(f"{self.prefix}*"):
                keys.append(key)
            
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0
    
    async def delete_by_tags(self, tags: Set[str]) -> int:
        """按标签删除"""
        try:
            count = 0
            for tag in tags:
                tag_key = f"{self.prefix}tag:{tag}"
                keys = await self.redis.smembers(tag_key)
                
                for key in keys:
                    if await self.delete(key.decode() if isinstance(key, bytes) else key):
                        count += 1
                
                await self.redis.delete(tag_key)
            
            return count
        except Exception as e:
            logger.error(f"Redis delete_by_tags error: {e}")
            return 0
    
    async def mget(self, keys: List[str]) -> Dict[str, Optional[T]]:
        """批量获取"""
        try:
            redis_keys = [self._make_key(k) for k in keys]
            values = await self.redis.mget(redis_keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)
                    self._stats.hits += 1
                else:
                    result[key] = None
                    self._stats.misses += 1
            
            return result
        except Exception as e:
            logger.error(f"Redis mget error: {e}")
            return {k: None for k in keys}
    
    async def mset(
        self,
        items: Dict[str, T],
        ttl: Optional[int] = None
    ) -> bool:
        """批量设置"""
        try:
            pipe = self.redis.pipeline()
            ex = ttl or self.default_ttl
            
            for key, value in items.items():
                data = self._serialize(value)
                pipe.set(self._make_key(key), data, ex=ex)
            
            await pipe.execute()
            self._stats.sets += len(items)
            return True
        except Exception as e:
            logger.error(f"Redis mset error: {e}")
            return False
    
    def get_stats(self) -> CacheStats:
        """获取统计"""
        return self._stats


# ==================== 多级缓存 ====================

class MultiTierCache(CacheBackend[T]):
    """多级缓存 - L1内存 + L2本地 + L3分布式"""
    
    def __init__(
        self,
        l1_cache: Optional[MemoryCache] = None,
        l2_cache: Optional[CacheBackend] = None,
        l3_cache: Optional[RedisCache] = None
    ):
        self.l1 = l1_cache or MemoryCache(max_size=1000, max_memory_mb=64)
        self.l2 = l2_cache
        self.l3 = l3_cache
        self._stats = CacheStats()
    
    async def get(self, key: str) -> Optional[T]:
        """层级获取"""
        # L1
        value = await self.l1.get(key)
        if value is not None:
            return value
        
        # L2
        if self.l2:
            value = await self.l2.get(key)
            if value is not None:
                # 回填L1
                await self.l1.set(key, value)
                return value
        
        # L3
        if self.l3:
            value = await self.l3.get(key)
            if value is not None:
                # 回填L1, L2
                await self.l1.set(key, value)
                if self.l2:
                    await self.l2.set(key, value)
                return value
        
        self._stats.misses += 1
        return None
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None
    ) -> bool:
        """写入所有层级"""
        results = []
        
        # L1
        results.append(await self.l1.set(key, value, ttl, tags))
        
        # L2
        if self.l2:
            results.append(await self.l2.set(key, value, ttl, tags))
        
        # L3
        if self.l3:
            results.append(await self.l3.set(key, value, ttl, tags))
        
        self._stats.sets += 1
        return all(results)
    
    async def delete(self, key: str) -> bool:
        """从所有层级删除"""
        results = []
        
        results.append(await self.l1.delete(key))
        
        if self.l2:
            results.append(await self.l2.delete(key))
        
        if self.l3:
            results.append(await self.l3.delete(key))
        
        self._stats.deletes += 1
        return any(results)
    
    async def exists(self, key: str) -> bool:
        """检查是否存在"""
        if await self.l1.exists(key):
            return True
        if self.l2 and await self.l2.exists(key):
            return True
        if self.l3 and await self.l3.exists(key):
            return True
        return False
    
    async def clear(self) -> int:
        """清空所有层级"""
        count = await self.l1.clear()
        
        if self.l2:
            count += await self.l2.clear()
        
        if self.l3:
            count += await self.l3.clear()
        
        return count
    
    def get_stats(self) -> CacheStats:
        """获取统计"""
        return self._stats


# ==================== 缓存防护 ====================

class BloomFilter:
    """布隆过滤器 - 防缓存穿透"""
    
    def __init__(self, expected_items: int = 100000, false_positive_rate: float = 0.01):
        import math
        
        # 计算最优参数
        self.size = int(-expected_items * math.log(false_positive_rate) / (math.log(2) ** 2))
        self.hash_count = int((self.size / expected_items) * math.log(2))
        self.bit_array = [False] * self.size
    
    def _hashes(self, item: str) -> List[int]:
        """生成多个哈希值"""
        hashes = []
        for i in range(self.hash_count):
            h = hashlib.md5(f"{item}:{i}".encode()).hexdigest()
            hashes.append(int(h, 16) % self.size)
        return hashes
    
    def add(self, item: str):
        """添加元素"""
        for h in self._hashes(item):
            self.bit_array[h] = True
    
    def contains(self, item: str) -> bool:
        """检查是否可能存在"""
        return all(self.bit_array[h] for h in self._hashes(item))


class CacheBreaker:
    """缓存击穿防护 - 互斥锁/预热"""
    
    def __init__(self, lock_timeout: float = 10.0):
        self.lock_timeout = lock_timeout
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock_manager = asyncio.Lock()
    
    async def get_lock(self, key: str) -> asyncio.Lock:
        """获取键对应的锁"""
        async with self._lock_manager:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]
    
    async def execute_with_lock(
        self,
        key: str,
        loader: Callable[[], T],
        cache: CacheBackend[T],
        ttl: int = 3600
    ) -> T:
        """使用互斥锁加载数据"""
        # 先尝试从缓存获取
        value = await cache.get(key)
        if value is not None:
            return value
        
        # 获取锁
        lock = await self.get_lock(key)
        
        try:
            async with asyncio.timeout(self.lock_timeout):
                async with lock:
                    # 双重检查
                    value = await cache.get(key)
                    if value is not None:
                        return value
                    
                    # 加载数据
                    if asyncio.iscoroutinefunction(loader):
                        value = await loader()
                    else:
                        value = loader()
                    
                    # 写入缓存
                    await cache.set(key, value, ttl)
                    return value
        except asyncio.TimeoutError:
            raise TimeoutError(f"获取锁超时: {key}")


class CacheWarmer:
    """缓存预热器"""
    
    def __init__(self, cache: CacheBackend):
        self.cache = cache
        self._warming_tasks: Dict[str, asyncio.Task] = {}
    
    async def warm(
        self,
        keys_loaders: Dict[str, Callable[[], T]],
        ttl: int = 3600,
        concurrency: int = 10
    ) -> Dict[str, bool]:
        """批量预热"""
        results = {}
        semaphore = asyncio.Semaphore(concurrency)
        
        async def warm_one(key: str, loader: Callable):
            async with semaphore:
                try:
                    if asyncio.iscoroutinefunction(loader):
                        value = await loader()
                    else:
                        value = loader()
                    
                    await self.cache.set(key, value, ttl)
                    return True
                except Exception as e:
                    logger.error(f"预热失败 {key}: {e}")
                    return False
        
        tasks = [
            warm_one(key, loader)
            for key, loader in keys_loaders.items()
        ]
        
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for key, result in zip(keys_loaders.keys(), task_results):
            results[key] = result is True
        
        return results
    
    async def schedule_warm(
        self,
        key: str,
        loader: Callable[[], T],
        ttl: int = 3600,
        refresh_before: int = 300
    ):
        """定时刷新预热"""
        async def refresh_loop():
            while True:
                try:
                    await asyncio.sleep(ttl - refresh_before)
                    
                    if asyncio.iscoroutinefunction(loader):
                        value = await loader()
                    else:
                        value = loader()
                    
                    await self.cache.set(key, value, ttl)
                    logger.debug(f"缓存刷新: {key}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"缓存刷新失败 {key}: {e}")
        
        # 取消旧任务
        if key in self._warming_tasks:
            self._warming_tasks[key].cancel()
        
        # 创建新任务
        task = asyncio.create_task(refresh_loop())
        self._warming_tasks[key] = task
    
    async def stop_all(self):
        """停止所有预热任务"""
        for task in self._warming_tasks.values():
            task.cancel()
        self._warming_tasks.clear()


# ==================== 缓存装饰器 ====================

def cached(
    cache: CacheBackend,
    ttl: int = 3600,
    key_builder: Optional[Callable[..., str]] = None,
    tags: Optional[Set[str]] = None
):
    """缓存装饰器"""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                key_parts = [fn.__module__, fn.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # 尝试从缓存获取
            value = await cache.get(cache_key)
            if value is not None:
                return value
            
            # 执行函数
            if asyncio.iscoroutinefunction(fn):
                value = await fn(*args, **kwargs)
            else:
                value = fn(*args, **kwargs)
            
            # 写入缓存
            await cache.set(cache_key, value, ttl, tags)
            return value
        
        return wrapper
    return decorator


def cache_aside(
    cache: CacheBackend,
    ttl: int = 3600,
    null_ttl: int = 60,
    breaker: Optional[CacheBreaker] = None
):
    """Cache-Aside模式装饰器"""
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [fn.__module__, fn.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # 使用互斥锁
            if breaker:
                async def loader():
                    if asyncio.iscoroutinefunction(fn):
                        return await fn(*args, **kwargs)
                    return fn(*args, **kwargs)
                
                return await breaker.execute_with_lock(
                    cache_key, loader, cache, ttl
                )
            
            # 尝试从缓存获取
            value = await cache.get(cache_key)
            if value is not None:
                if value == "__NULL__":
                    return None
                return value
            
            # 执行函数
            if asyncio.iscoroutinefunction(fn):
                value = await fn(*args, **kwargs)
            else:
                value = fn(*args, **kwargs)
            
            # 写入缓存(包括空值)
            if value is None:
                await cache.set(cache_key, "__NULL__", null_ttl)
            else:
                await cache.set(cache_key, value, ttl)
            
            return value
        
        return wrapper
    return decorator


# ==================== 缓存管理器 ====================

class CacheManager:
    """缓存管理器 - 统一管理多个缓存"""
    
    def __init__(self):
        self._caches: Dict[str, CacheBackend] = {}
        self._bloom_filter: Optional[BloomFilter] = None
        self._breaker = CacheBreaker()
        self._warmers: Dict[str, CacheWarmer] = {}
    
    def register(self, name: str, cache: CacheBackend):
        """注册缓存"""
        self._caches[name] = cache
        self._warmers[name] = CacheWarmer(cache)
        logger.info(f"注册缓存: {name}")
    
    def get_cache(self, name: str) -> Optional[CacheBackend]:
        """获取缓存"""
        return self._caches.get(name)
    
    def enable_bloom_filter(self, expected_items: int = 100000):
        """启用布隆过滤器"""
        self._bloom_filter = BloomFilter(expected_items)
    
    async def get(
        self,
        cache_name: str,
        key: str,
        loader: Optional[Callable[[], T]] = None,
        ttl: int = 3600,
        use_bloom: bool = True
    ) -> Optional[T]:
        """智能获取缓存"""
        cache = self._caches.get(cache_name)
        if not cache:
            raise ValueError(f"缓存不存在: {cache_name}")
        
        # 布隆过滤器检查
        if use_bloom and self._bloom_filter:
            if not self._bloom_filter.contains(key):
                return None
        
        # 使用互斥锁加载
        if loader:
            return await self._breaker.execute_with_lock(
                f"{cache_name}:{key}",
                loader,
                cache,
                ttl
            )
        
        return await cache.get(key)
    
    async def set(
        self,
        cache_name: str,
        key: str,
        value: T,
        ttl: int = 3600,
        tags: Optional[Set[str]] = None
    ) -> bool:
        """设置缓存"""
        cache = self._caches.get(cache_name)
        if not cache:
            raise ValueError(f"缓存不存在: {cache_name}")
        
        # 添加到布隆过滤器
        if self._bloom_filter:
            self._bloom_filter.add(key)
        
        return await cache.set(key, value, ttl, tags)
    
    async def warm(
        self,
        cache_name: str,
        keys_loaders: Dict[str, Callable[[], T]],
        ttl: int = 3600
    ) -> Dict[str, bool]:
        """预热缓存"""
        warmer = self._warmers.get(cache_name)
        if not warmer:
            raise ValueError(f"缓存不存在: {cache_name}")
        
        return await warmer.warm(keys_loaders, ttl)
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有缓存统计"""
        return {
            name: {
                "hits": cache.get_stats().hits,
                "misses": cache.get_stats().misses,
                "hit_rate": cache.get_stats().hit_rate,
                "size": cache.get_stats().size
            }
            for name, cache in self._caches.items()
        }
    
    async def clear_all(self):
        """清空所有缓存"""
        for name, cache in self._caches.items():
            await cache.clear()
            logger.info(f"清空缓存: {name}")


# ==================== 全局实例 ====================

cache_manager = CacheManager()


# ==================== 导出 ====================

__all__ = [
    # 枚举
    "EvictionPolicy",
    "CacheLevel",
    # 数据类
    "CacheEntry",
    "CacheStats",
    # 缓存后端
    "CacheBackend",
    "MemoryCache",
    "RedisCache",
    "MultiTierCache",
    # 防护
    "BloomFilter",
    "CacheBreaker",
    "CacheWarmer",
    # 装饰器
    "cached",
    "cache_aside",
    # 管理器
    "CacheManager",
    "cache_manager",
]
