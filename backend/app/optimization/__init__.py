"""
系统优化模块 - 全面性能优化
System Optimization Module - Comprehensive Performance Enhancement

包含:
- performance: 性能优化 - 连接池、查询优化、异步优化
- caching: 高级缓存 - Redis集群、缓存预热、防穿透
- middleware: API中间件 - 限流、压缩、请求追踪
- database: 数据库优化 - 索引分析、慢查询、分表策略
- config_center: 配置中心 - 特性开关、动态配置
- health: 健康检查 - 深度检查、自动恢复
"""

from .performance import (
    # 连接池
    PoolStatus, PoolStats, ConnectionWrapper, ConnectionPool,
    # 查询优化
    QueryPlan, QueryOptimizer,
    # 异步优化
    AsyncBatcher, AsyncThrottler, AsyncRetrier,
    # 资源管理
    ResourceManager,
    # 性能监控
    PerformanceMetric, PerformanceMonitor,
    # 全局实例
    resource_manager, query_optimizer, performance_monitor,
)

from .caching import (
    # 枚举
    EvictionPolicy, CacheLevel,
    # 数据类
    CacheEntry, CacheStats,
    # 缓存后端
    CacheBackend, MemoryCache, RedisCache, MultiTierCache,
    # 防护
    BloomFilter, CacheBreaker, CacheWarmer,
    # 装饰器
    cached, cache_aside,
    # 管理器
    CacheManager, cache_manager,
)

from .middleware import (
    # 请求追踪
    RequestTracingMiddleware,
    # 限流
    RateLimitAlgorithm, RateLimitRule, RateLimiter, RateLimitMiddleware,
    # 压缩
    CompressionMiddleware,
    # CORS
    CORSConfig, EnhancedCORSMiddleware,
    # 响应缓存
    ResponseCacheMiddleware,
    # 请求验证
    RequestValidationMiddleware,
    # 超时
    TimeoutMiddleware,
    # 管理器
    MiddlewareManager,
)

from .database import (
    # 索引分析
    IndexType, IndexInfo, IndexRecommendation, IndexAnalyzer,
    # 慢查询
    SlowQuery, SlowQueryAnalyzer,
    # 分片
    ShardingStrategy, ShardConfig, ShardRouter, ShardManager,
    # 配置
    DatabaseConfig,
    # 管理器
    DatabaseOptimizer,
)

from .config_center import (
    # 配置源
    ConfigSource, EnvConfigSource, FileConfigSource, RedisConfigSource,
    # 特性开关
    FeatureStatus, FeatureFlag, FeatureFlagManager,
    # 动态配置
    ConfigItem, DynamicConfig,
    # 环境管理
    Environment, EnvironmentConfig, EnvironmentManager,
    # 配置中心
    ConfigCenter, config_center,
)

from .health import (
    # 状态枚举
    HealthStatus, CheckType,
    # 数据类
    CheckResult, HealthReport, RecoveryAction,
    # 检查器
    HealthChecker, DatabaseChecker, RedisChecker, HTTPChecker,
    TCPChecker, DiskChecker, MemoryChecker, CPUChecker, CustomChecker,
    # 自动恢复
    AutoRecovery,
    # 管理器
    HealthManager, health_manager,
    # 路由
    create_health_routes,
)


# ==================== 统一优化管理器 ====================

class OptimizationManager:
    """
    系统优化管理器 - 统一管理所有优化组件
    
    提供:
    - 性能优化: 连接池、查询优化、异步处理
    - 缓存管理: 多级缓存、预热、防穿透
    - 中间件: 限流、压缩、追踪
    - 数据库: 索引分析、慢查询、分表
    - 配置中心: 特性开关、动态配置
    - 健康检查: 深度检查、自动恢复
    """
    
    def __init__(self):
        self.resources = resource_manager
        self.cache = cache_manager
        self.config = config_center
        self.health = health_manager
        self.query_optimizer = query_optimizer
        self.performance = performance_monitor
    
    async def initialize(self, **kwargs):
        """初始化所有优化组件"""
        # 初始化配置中心
        await self.config.initialize(
            config_file=kwargs.get('config_file'),
            redis_client=kwargs.get('redis_client')
        )
        
        # 注册默认缓存
        self.cache.register('default', MemoryCache(max_size=5000))
        
        # 注册健康检查
        self.health.register(MemoryChecker(warning_threshold=80))
        self.health.register(DiskChecker(warning_threshold=80))
        self.health.register(CPUChecker(warning_threshold=85))
        
        # 启动后台健康检查
        await self.health.start_background_checks(interval=60)
    
    def get_status(self) -> dict:
        """获取优化系统状态"""
        return {
            "resources": self.resources.get_status(),
            "cache": self.cache.get_all_stats(),
            "config": self.config.get_status(),
            "health": self.health.get_last_results(),
            "performance": self.performance.get_all_stats()
        }
    
    async def shutdown(self):
        """关闭优化系统"""
        await self.health.stop_background_checks()
        await self.config.config.stop_auto_refresh()
        await self.resources.cleanup()


# 全局实例
optimization_manager = OptimizationManager()


# ==================== 导出 ====================

__all__ = [
    # ===== 性能优化 =====
    "PoolStatus", "PoolStats", "ConnectionWrapper", "ConnectionPool",
    "QueryPlan", "QueryOptimizer",
    "AsyncBatcher", "AsyncThrottler", "AsyncRetrier",
    "ResourceManager", "resource_manager",
    "PerformanceMetric", "PerformanceMonitor", "performance_monitor",
    "query_optimizer",
    
    # ===== 缓存 =====
    "EvictionPolicy", "CacheLevel",
    "CacheEntry", "CacheStats",
    "CacheBackend", "MemoryCache", "RedisCache", "MultiTierCache",
    "BloomFilter", "CacheBreaker", "CacheWarmer",
    "cached", "cache_aside",
    "CacheManager", "cache_manager",
    
    # ===== 中间件 =====
    "RequestTracingMiddleware",
    "RateLimitAlgorithm", "RateLimitRule", "RateLimiter", "RateLimitMiddleware",
    "CompressionMiddleware",
    "CORSConfig", "EnhancedCORSMiddleware",
    "ResponseCacheMiddleware",
    "RequestValidationMiddleware",
    "TimeoutMiddleware",
    "MiddlewareManager",
    
    # ===== 数据库 =====
    "IndexType", "IndexInfo", "IndexRecommendation", "IndexAnalyzer",
    "SlowQuery", "SlowQueryAnalyzer",
    "ShardingStrategy", "ShardConfig", "ShardRouter", "ShardManager",
    "DatabaseConfig", "DatabaseOptimizer",
    
    # ===== 配置中心 =====
    "ConfigSource", "EnvConfigSource", "FileConfigSource", "RedisConfigSource",
    "FeatureStatus", "FeatureFlag", "FeatureFlagManager",
    "ConfigItem", "DynamicConfig",
    "Environment", "EnvironmentConfig", "EnvironmentManager",
    "ConfigCenter", "config_center",
    
    # ===== 健康检查 =====
    "HealthStatus", "CheckType",
    "CheckResult", "HealthReport", "RecoveryAction",
    "HealthChecker", "DatabaseChecker", "RedisChecker", "HTTPChecker",
    "TCPChecker", "DiskChecker", "MemoryChecker", "CPUChecker", "CustomChecker",
    "AutoRecovery",
    "HealthManager", "health_manager",
    "create_health_routes",
    
    # ===== 统一管理 =====
    "OptimizationManager",
    "optimization_manager",
]
