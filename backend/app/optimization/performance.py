"""
性能优化模块 - 连接池、查询优化、异步优化、资源管理
Performance Optimization - Connection Pool, Query Optimization, Async Enhancement
"""

import asyncio
import functools
import gc
import sys
import threading
import time
import weakref
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Callable, Dict, Generic, List, Optional, 
    Set, Tuple, TypeVar, Union, Coroutine
)
import logging
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ==================== 连接池管理 ====================

class PoolStatus(str, Enum):
    """连接池状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CLOSED = "closed"


@dataclass
class PoolStats:
    """连接池统计"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_requests: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_wait_time_ms: float = 0.0
    avg_use_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


class ConnectionWrapper(Generic[T]):
    """连接包装器"""
    
    def __init__(
        self,
        connection: T,
        pool: "ConnectionPool",
        created_at: datetime = None
    ):
        self.connection = connection
        self.pool = pool
        self.created_at = created_at or datetime.now()
        self.last_used = self.created_at
        self.use_count = 0
        self.is_valid = True
    
    async def __aenter__(self) -> T:
        self.last_used = datetime.now()
        self.use_count += 1
        return self.connection
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.pool.release(self)
    
    def is_expired(self, max_lifetime: timedelta) -> bool:
        """检查是否过期"""
        return datetime.now() - self.created_at > max_lifetime
    
    def is_idle_timeout(self, idle_timeout: timedelta) -> bool:
        """检查是否空闲超时"""
        return datetime.now() - self.last_used > idle_timeout


class ConnectionPool(Generic[T]):
    """通用异步连接池"""
    
    def __init__(
        self,
        factory: Callable[[], Coroutine[Any, Any, T]],
        validator: Optional[Callable[[T], Coroutine[Any, Any, bool]]] = None,
        destructor: Optional[Callable[[T], Coroutine[Any, Any, None]]] = None,
        min_size: int = 5,
        max_size: int = 20,
        max_lifetime: timedelta = timedelta(hours=1),
        idle_timeout: timedelta = timedelta(minutes=10),
        acquire_timeout: float = 30.0,
        name: str = "default"
    ):
        self.factory = factory
        self.validator = validator
        self.destructor = destructor
        self.min_size = min_size
        self.max_size = max_size
        self.max_lifetime = max_lifetime
        self.idle_timeout = idle_timeout
        self.acquire_timeout = acquire_timeout
        self.name = name
        
        self._pool: asyncio.Queue[ConnectionWrapper[T]] = asyncio.Queue()
        self._all_connections: Set[ConnectionWrapper[T]] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        self._stats = PoolStats()
        self._wait_times: List[float] = []
        self._use_times: List[float] = []
        
        # 后台维护任务
        self._maintenance_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """初始化连接池"""
        async with self._lock:
            for _ in range(self.min_size):
                try:
                    conn = await self._create_connection()
                    await self._pool.put(conn)
                except Exception as e:
                    logger.error(f"连接池 {self.name} 初始化失败: {e}")
        
        # 启动维护任务
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        logger.info(f"连接池 {self.name} 初始化完成, 大小: {self._pool.qsize()}")
    
    async def _create_connection(self) -> ConnectionWrapper[T]:
        """创建新连接"""
        conn = await self.factory()
        wrapper = ConnectionWrapper(conn, self)
        self._all_connections.add(wrapper)
        self._stats.total_connections = len(self._all_connections)
        return wrapper
    
    async def acquire(self) -> ConnectionWrapper[T]:
        """获取连接"""
        if self._closed:
            raise RuntimeError(f"连接池 {self.name} 已关闭")
        
        start_time = time.monotonic()
        self._stats.waiting_requests += 1
        self._stats.total_requests += 1
        
        try:
            # 尝试从池中获取
            while True:
                try:
                    wrapper = await asyncio.wait_for(
                        self._pool.get(),
                        timeout=self.acquire_timeout
                    )
                    
                    # 验证连接
                    if not wrapper.is_valid:
                        await self._destroy_connection(wrapper)
                        continue
                    
                    if wrapper.is_expired(self.max_lifetime):
                        await self._destroy_connection(wrapper)
                        continue
                    
                    if self.validator:
                        try:
                            if not await self.validator(wrapper.connection):
                                await self._destroy_connection(wrapper)
                                continue
                        except Exception:
                            await self._destroy_connection(wrapper)
                            continue
                    
                    wait_time = (time.monotonic() - start_time) * 1000
                    self._wait_times.append(wait_time)
                    if len(self._wait_times) > 1000:
                        self._wait_times = self._wait_times[-500:]
                    self._stats.avg_wait_time_ms = sum(self._wait_times) / len(self._wait_times)
                    
                    return wrapper
                    
                except asyncio.TimeoutError:
                    # 尝试创建新连接
                    async with self._lock:
                        if len(self._all_connections) < self.max_size:
                            wrapper = await self._create_connection()
                            return wrapper
                    
                    raise asyncio.TimeoutError(
                        f"连接池 {self.name} 获取连接超时"
                    )
        finally:
            self._stats.waiting_requests -= 1
    
    async def release(self, wrapper: ConnectionWrapper[T]):
        """释放连接"""
        if self._closed:
            await self._destroy_connection(wrapper)
            return
        
        if not wrapper.is_valid or wrapper.is_expired(self.max_lifetime):
            await self._destroy_connection(wrapper)
            return
        
        await self._pool.put(wrapper)
    
    async def _destroy_connection(self, wrapper: ConnectionWrapper[T]):
        """销毁连接"""
        wrapper.is_valid = False
        self._all_connections.discard(wrapper)
        self._stats.total_connections = len(self._all_connections)
        
        if self.destructor:
            try:
                await self.destructor(wrapper.connection)
            except Exception as e:
                logger.error(f"销毁连接失败: {e}")
    
    async def _maintenance_loop(self):
        """后台维护循环"""
        while not self._closed:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_idle_connections()
                await self._ensure_min_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"连接池维护错误: {e}")
    
    async def _cleanup_idle_connections(self):
        """清理空闲连接"""
        to_cleanup = []
        temp_pool = []
        
        while not self._pool.empty():
            try:
                wrapper = self._pool.get_nowait()
                if wrapper.is_idle_timeout(self.idle_timeout):
                    to_cleanup.append(wrapper)
                else:
                    temp_pool.append(wrapper)
            except asyncio.QueueEmpty:
                break
        
        # 放回有效连接
        for wrapper in temp_pool:
            await self._pool.put(wrapper)
        
        # 销毁空闲连接
        for wrapper in to_cleanup:
            await self._destroy_connection(wrapper)
    
    async def _ensure_min_connections(self):
        """确保最小连接数"""
        async with self._lock:
            while len(self._all_connections) < self.min_size:
                try:
                    conn = await self._create_connection()
                    await self._pool.put(conn)
                except Exception as e:
                    logger.error(f"创建最小连接失败: {e}")
                    break
    
    async def close(self):
        """关闭连接池"""
        self._closed = True
        
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        # 销毁所有连接
        for wrapper in list(self._all_connections):
            await self._destroy_connection(wrapper)
        
        logger.info(f"连接池 {self.name} 已关闭")
    
    def get_stats(self) -> PoolStats:
        """获取统计信息"""
        self._stats.idle_connections = self._pool.qsize()
        self._stats.active_connections = len(self._all_connections) - self._pool.qsize()
        return self._stats
    
    def get_status(self) -> PoolStatus:
        """获取池状态"""
        if self._closed:
            return PoolStatus.CLOSED
        
        stats = self.get_stats()
        if stats.active_connections >= self.max_size * 0.9:
            return PoolStatus.UNHEALTHY
        elif stats.active_connections >= self.max_size * 0.7:
            return PoolStatus.DEGRADED
        return PoolStatus.HEALTHY


# ==================== 查询优化器 ====================

@dataclass
class QueryPlan:
    """查询计划"""
    original_query: str
    optimized_query: str
    estimated_cost: float
    optimizations_applied: List[str]
    created_at: datetime = field(default_factory=datetime.now)


class QueryOptimizer:
    """SQL查询优化器"""
    
    def __init__(self):
        self.query_cache: Dict[str, QueryPlan] = {}
        self.query_stats: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "total_time_ms": 0,
            "avg_time_ms": 0,
            "max_time_ms": 0
        })
    
    def optimize(self, query: str) -> QueryPlan:
        """优化查询"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        if query_hash in self.query_cache:
            return self.query_cache[query_hash]
        
        optimizations = []
        optimized = query
        
        # 1. 移除多余空格
        import re
        optimized = re.sub(r'\s+', ' ', optimized).strip()
        if optimized != query:
            optimizations.append("whitespace_cleanup")
        
        # 2. SELECT * 优化建议
        if re.search(r'SELECT\s+\*', optimized, re.IGNORECASE):
            optimizations.append("suggest_explicit_columns")
        
        # 3. LIKE '%xxx%' 优化建议
        if re.search(r"LIKE\s+'%[^']+%'", optimized, re.IGNORECASE):
            optimizations.append("suggest_fulltext_search")
        
        # 4. 子查询优化建议
        if optimized.lower().count('select') > 1:
            optimizations.append("suggest_join_rewrite")
        
        # 5. ORDER BY + LIMIT 优化
        if 'ORDER BY' in optimized.upper() and 'LIMIT' in optimized.upper():
            optimizations.append("suggest_index_for_sort")
        
        # 6. 大表JOIN优化建议
        if 'JOIN' in optimized.upper():
            optimizations.append("suggest_join_order_analysis")
        
        plan = QueryPlan(
            original_query=query,
            optimized_query=optimized,
            estimated_cost=self._estimate_cost(optimized),
            optimizations_applied=optimizations
        )
        
        self.query_cache[query_hash] = plan
        return plan
    
    def _estimate_cost(self, query: str) -> float:
        """估算查询成本"""
        cost = 1.0
        query_upper = query.upper()
        
        # JOIN增加成本
        cost += query_upper.count('JOIN') * 2.0
        
        # 子查询增加成本
        cost += (query_upper.count('SELECT') - 1) * 1.5
        
        # 聚合函数增加成本
        for func in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'GROUP BY']:
            if func in query_upper:
                cost += 0.5
        
        # LIKE模糊查询增加成本
        if 'LIKE' in query_upper:
            cost += 1.0
        
        # ORDER BY增加成本
        if 'ORDER BY' in query_upper:
            cost += 0.5
        
        return cost
    
    def record_execution(self, query: str, execution_time_ms: float):
        """记录查询执行"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        stats = self.query_stats[query_hash]
        
        stats["count"] += 1
        stats["total_time_ms"] += execution_time_ms
        stats["avg_time_ms"] = stats["total_time_ms"] / stats["count"]
        stats["max_time_ms"] = max(stats["max_time_ms"], execution_time_ms)
    
    def get_slow_queries(self, threshold_ms: float = 1000) -> List[Dict]:
        """获取慢查询"""
        slow = []
        for query_hash, stats in self.query_stats.items():
            if stats["avg_time_ms"] > threshold_ms:
                slow.append({
                    "query_hash": query_hash,
                    **stats
                })
        return sorted(slow, key=lambda x: x["avg_time_ms"], reverse=True)


# ==================== 异步优化器 ====================

class AsyncBatcher(Generic[T]):
    """异步批处理器"""
    
    def __init__(
        self,
        batch_fn: Callable[[List[T]], Coroutine[Any, Any, List[Any]]],
        max_batch_size: int = 100,
        max_wait_time: float = 0.1
    ):
        self.batch_fn = batch_fn
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        
        self._pending: List[Tuple[T, asyncio.Future]] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = True
    
    async def submit(self, item: T) -> Any:
        """提交单个项目"""
        future = asyncio.get_event_loop().create_future()
        
        async with self._lock:
            self._pending.append((item, future))
            
            if len(self._pending) >= self.max_batch_size:
                await self._flush()
            elif self._flush_task is None:
                self._flush_task = asyncio.create_task(self._delayed_flush())
        
        return await future
    
    async def _delayed_flush(self):
        """延迟刷新"""
        await asyncio.sleep(self.max_wait_time)
        async with self._lock:
            if self._pending:
                await self._flush()
            self._flush_task = None
    
    async def _flush(self):
        """刷新批处理"""
        if not self._pending:
            return
        
        items = [item for item, _ in self._pending]
        futures = [future for _, future in self._pending]
        self._pending = []
        
        try:
            results = await self.batch_fn(items)
            for future, result in zip(futures, results):
                if not future.done():
                    future.set_result(result)
        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)
    
    async def close(self):
        """关闭批处理器"""
        self._running = False
        async with self._lock:
            if self._pending:
                await self._flush()
            if self._flush_task:
                self._flush_task.cancel()


class AsyncThrottler:
    """异步节流器"""
    
    def __init__(
        self,
        rate_limit: int,
        time_window: float = 1.0,
        burst_limit: Optional[int] = None
    ):
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.burst_limit = burst_limit or rate_limit * 2
        
        self._tokens = float(rate_limit)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """获取令牌，返回等待时间"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            
            # 补充令牌
            self._tokens = min(
                self.burst_limit,
                self._tokens + elapsed * (self.rate_limit / self.time_window)
            )
            self._last_update = now
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0
            
            # 计算等待时间
            wait_time = (tokens - self._tokens) * (self.time_window / self.rate_limit)
            await asyncio.sleep(wait_time)
            
            self._tokens = 0
            return wait_time
    
    def throttle(self, fn: Callable) -> Callable:
        """装饰器：节流函数"""
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await fn(*args, **kwargs)
        return wrapper


class AsyncRetrier:
    """异步重试器"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_exceptions: Tuple[type, ...] = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions
    
    async def execute(
        self,
        fn: Callable[[], Coroutine[Any, Any, T]],
        on_retry: Optional[Callable[[int, Exception], None]] = None
    ) -> T:
        """执行并重试"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await fn()
            except self.retryable_exceptions as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    
                    if on_retry:
                        on_retry(attempt + 1, e)
                    
                    logger.warning(
                        f"重试 {attempt + 1}/{self.max_retries}, "
                        f"等待 {delay:.2f}s, 错误: {e}"
                    )
                    await asyncio.sleep(delay)
        
        raise last_exception
    
    def retry(
        self,
        on_retry: Optional[Callable[[int, Exception], None]] = None
    ) -> Callable:
        """装饰器：自动重试"""
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                return await self.execute(
                    lambda: fn(*args, **kwargs),
                    on_retry
                )
            return wrapper
        return decorator


# ==================== 资源管理器 ====================

class ResourceManager:
    """资源管理器 - 统一管理系统资源"""
    
    def __init__(self):
        self._resources: Dict[str, Any] = {}
        self._pools: Dict[str, ConnectionPool] = {}
        self._executors: Dict[str, ThreadPoolExecutor] = {}
        self._cleanup_callbacks: List[Callable] = []
        self._lock = threading.Lock()
    
    def register_resource(self, name: str, resource: Any):
        """注册资源"""
        with self._lock:
            self._resources[name] = resource
    
    def get_resource(self, name: str) -> Optional[Any]:
        """获取资源"""
        return self._resources.get(name)
    
    def register_pool(self, name: str, pool: ConnectionPool):
        """注册连接池"""
        with self._lock:
            self._pools[name] = pool
    
    def get_pool(self, name: str) -> Optional[ConnectionPool]:
        """获取连接池"""
        return self._pools.get(name)
    
    def get_executor(
        self,
        name: str = "default",
        max_workers: int = None
    ) -> ThreadPoolExecutor:
        """获取线程池执行器"""
        if name not in self._executors:
            with self._lock:
                if name not in self._executors:
                    self._executors[name] = ThreadPoolExecutor(
                        max_workers=max_workers,
                        thread_name_prefix=f"pool-{name}-"
                    )
        return self._executors[name]
    
    def on_cleanup(self, callback: Callable):
        """注册清理回调"""
        self._cleanup_callbacks.append(callback)
    
    async def cleanup(self):
        """清理所有资源"""
        # 关闭连接池
        for name, pool in self._pools.items():
            try:
                await pool.close()
                logger.info(f"连接池 {name} 已关闭")
            except Exception as e:
                logger.error(f"关闭连接池 {name} 失败: {e}")
        
        # 关闭线程池
        for name, executor in self._executors.items():
            try:
                executor.shutdown(wait=True)
                logger.info(f"线程池 {name} 已关闭")
            except Exception as e:
                logger.error(f"关闭线程池 {name} 失败: {e}")
        
        # 执行清理回调
        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"清理回调执行失败: {e}")
        
        # 强制GC
        gc.collect()
        logger.info("资源清理完成")
    
    def get_status(self) -> Dict[str, Any]:
        """获取资源状态"""
        return {
            "resources": list(self._resources.keys()),
            "pools": {
                name: pool.get_status().value
                for name, pool in self._pools.items()
            },
            "executors": list(self._executors.keys())
        }


# ==================== 性能监控 ====================

@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self._timers: Dict[str, float] = {}
    
    def record(self, name: str, value: float, unit: str = ""):
        """记录指标"""
        metric = PerformanceMetric(name, value, unit)
        self._metrics[name].append(metric)
        
        # 保持历史记录在限制内
        if len(self._metrics[name]) > self.max_history:
            self._metrics[name] = self._metrics[name][-self.max_history//2:]
    
    def start_timer(self, name: str):
        """启动计时器"""
        self._timers[name] = time.perf_counter()
    
    def stop_timer(self, name: str) -> float:
        """停止计时器并记录"""
        if name not in self._timers:
            return 0.0
        
        elapsed = (time.perf_counter() - self._timers[name]) * 1000
        del self._timers[name]
        
        self.record(f"{name}_duration", elapsed, "ms")
        return elapsed
    
    @contextmanager
    def measure(self, name: str):
        """上下文管理器：测量执行时间"""
        self.start_timer(name)
        try:
            yield
        finally:
            self.stop_timer(name)
    
    @asynccontextmanager
    async def measure_async(self, name: str):
        """异步上下文管理器：测量执行时间"""
        self.start_timer(name)
        try:
            yield
        finally:
            self.stop_timer(name)
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """获取指标统计"""
        metrics = self._metrics.get(name, [])
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1]
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """获取所有指标统计"""
        return {name: self.get_stats(name) for name in self._metrics}


# ==================== 全局实例 ====================

resource_manager = ResourceManager()
query_optimizer = QueryOptimizer()
performance_monitor = PerformanceMonitor()


# ==================== 导出 ====================

__all__ = [
    # 连接池
    "PoolStatus",
    "PoolStats",
    "ConnectionWrapper",
    "ConnectionPool",
    # 查询优化
    "QueryPlan",
    "QueryOptimizer",
    # 异步优化
    "AsyncBatcher",
    "AsyncThrottler",
    "AsyncRetrier",
    # 资源管理
    "ResourceManager",
    # 性能监控
    "PerformanceMetric",
    "PerformanceMonitor",
    # 全局实例
    "resource_manager",
    "query_optimizer",
    "performance_monitor",
]
