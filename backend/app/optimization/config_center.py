"""
配置中心 - 特性开关、动态配置、环境管理
Configuration Center - Feature Flags, Dynamic Config, Environment Management
"""

import asyncio
import hashlib
import json
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar, Union
import logging
import yaml

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ==================== 配置源 ====================

class ConfigSource(ABC):
    """配置源基类"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取配置"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any) -> bool:
        """设置配置"""
        pass
    
    @abstractmethod
    async def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        pass


class EnvConfigSource(ConfigSource):
    """环境变量配置源"""
    
    def __init__(self, prefix: str = "APP_"):
        self.prefix = prefix
    
    async def get(self, key: str) -> Optional[str]:
        env_key = f"{self.prefix}{key.upper().replace('.', '_')}"
        return os.environ.get(env_key)
    
    async def set(self, key: str, value: Any) -> bool:
        env_key = f"{self.prefix}{key.upper().replace('.', '_')}"
        os.environ[env_key] = str(value)
        return True
    
    async def get_all(self) -> Dict[str, str]:
        return {
            k[len(self.prefix):].lower().replace('_', '.'): v
            for k, v in os.environ.items()
            if k.startswith(self.prefix)
        }


class FileConfigSource(ConfigSource):
    """文件配置源"""
    
    def __init__(
        self,
        file_path: str,
        auto_reload: bool = True,
        reload_interval: int = 60
    ):
        self.file_path = Path(file_path)
        self.auto_reload = auto_reload
        self.reload_interval = reload_interval
        self._config: Dict[str, Any] = {}
        self._last_modified: float = 0
        self._lock = asyncio.Lock()
    
    async def _load(self):
        """加载配置文件"""
        if not self.file_path.exists():
            return
        
        mtime = self.file_path.stat().st_mtime
        if mtime <= self._last_modified:
            return
        
        async with self._lock:
            try:
                content = self.file_path.read_text(encoding='utf-8')
                
                if self.file_path.suffix in ['.yaml', '.yml']:
                    self._config = yaml.safe_load(content) or {}
                elif self.file_path.suffix == '.json':
                    self._config = json.loads(content)
                else:
                    # 尝试作为key=value格式解析
                    self._config = {}
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self._config[key.strip()] = value.strip()
                
                self._last_modified = mtime
                logger.info(f"配置文件已加载: {self.file_path}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
    
    async def get(self, key: str) -> Optional[Any]:
        await self._load()
        
        # 支持点分隔的嵌套键
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    async def set(self, key: str, value: Any) -> bool:
        """设置配置(仅内存)"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        return True
    
    async def get_all(self) -> Dict[str, Any]:
        await self._load()
        return self._config.copy()
    
    async def save(self):
        """保存配置到文件"""
        async with self._lock:
            try:
                if self.file_path.suffix in ['.yaml', '.yml']:
                    content = yaml.dump(self._config, allow_unicode=True)
                else:
                    content = json.dumps(self._config, indent=2, ensure_ascii=False)
                
                self.file_path.write_text(content, encoding='utf-8')
                self._last_modified = time.time()
                return True
            except Exception as e:
                logger.error(f"保存配置失败: {e}")
                return False


class RedisConfigSource(ConfigSource):
    """Redis配置源"""
    
    def __init__(
        self,
        redis_client: Any,
        prefix: str = "config:",
        ttl: int = None
    ):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = ttl
    
    def _make_key(self, key: str) -> str:
        return f"{self.prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        try:
            value = await self.redis.get(self._make_key(key))
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis获取配置失败: {e}")
            return None
    
    async def set(self, key: str, value: Any) -> bool:
        try:
            await self.redis.set(
                self._make_key(key),
                json.dumps(value, ensure_ascii=False),
                ex=self.ttl
            )
            return True
        except Exception as e:
            logger.error(f"Redis设置配置失败: {e}")
            return False
    
    async def get_all(self) -> Dict[str, Any]:
        try:
            result = {}
            async for key in self.redis.scan_iter(f"{self.prefix}*"):
                short_key = key.decode().replace(self.prefix, "")
                value = await self.redis.get(key)
                if value:
                    result[short_key] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Redis获取所有配置失败: {e}")
            return {}


# ==================== 特性开关 ====================

class FeatureStatus(str, Enum):
    """特性状态"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    DATE_RANGE = "date_range"


@dataclass
class FeatureFlag:
    """特性开关"""
    name: str
    status: FeatureStatus
    description: str = ""
    percentage: float = 0.0  # 用于灰度发布
    user_list: Set[str] = field(default_factory=set)  # 白名单用户
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def is_enabled(self, user_id: str = None) -> bool:
        """检查是否启用"""
        if self.status == FeatureStatus.ENABLED:
            return True
        
        if self.status == FeatureStatus.DISABLED:
            return False
        
        if self.status == FeatureStatus.PERCENTAGE:
            if user_id:
                # 基于用户ID的一致性哈希
                hash_value = int(hashlib.md5(
                    f"{self.name}:{user_id}".encode()
                ).hexdigest(), 16)
                return (hash_value % 100) < self.percentage
            return False
        
        if self.status == FeatureStatus.USER_LIST:
            return user_id in self.user_list if user_id else False
        
        if self.status == FeatureStatus.DATE_RANGE:
            now = datetime.now()
            if self.start_date and now < self.start_date:
                return False
            if self.end_date and now > self.end_date:
                return False
            return True
        
        return False


class FeatureFlagManager:
    """特性开关管理器"""
    
    def __init__(self, config_source: Optional[ConfigSource] = None):
        self._flags: Dict[str, FeatureFlag] = {}
        self._config_source = config_source
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def load_from_source(self):
        """从配置源加载"""
        if not self._config_source:
            return
        
        flags_data = await self._config_source.get("feature_flags")
        if flags_data and isinstance(flags_data, dict):
            for name, data in flags_data.items():
                self._flags[name] = FeatureFlag(
                    name=name,
                    status=FeatureStatus(data.get("status", "disabled")),
                    description=data.get("description", ""),
                    percentage=data.get("percentage", 0.0),
                    user_list=set(data.get("user_list", [])),
                    start_date=datetime.fromisoformat(data["start_date"]) if data.get("start_date") else None,
                    end_date=datetime.fromisoformat(data["end_date"]) if data.get("end_date") else None,
                    metadata=data.get("metadata", {})
                )
    
    def register(self, flag: FeatureFlag):
        """注册特性开关"""
        self._flags[flag.name] = flag
        logger.info(f"注册特性开关: {flag.name} = {flag.status.value}")
    
    def is_enabled(self, name: str, user_id: str = None) -> bool:
        """检查特性是否启用"""
        flag = self._flags.get(name)
        if not flag:
            return False
        return flag.is_enabled(user_id)
    
    async def set_status(self, name: str, status: FeatureStatus):
        """设置特性状态"""
        async with self._lock:
            if name in self._flags:
                old_status = self._flags[name].status
                self._flags[name].status = status
                self._flags[name].updated_at = datetime.now()
                
                # 触发监听器
                if name in self._listeners:
                    for listener in self._listeners[name]:
                        try:
                            listener(name, old_status, status)
                        except Exception as e:
                            logger.error(f"特性监听器错误: {e}")
                
                logger.info(f"特性状态变更: {name} {old_status.value} -> {status.value}")
    
    async def set_percentage(self, name: str, percentage: float):
        """设置灰度百分比"""
        async with self._lock:
            if name in self._flags:
                self._flags[name].percentage = max(0, min(100, percentage))
                self._flags[name].status = FeatureStatus.PERCENTAGE
                self._flags[name].updated_at = datetime.now()
    
    def on_change(self, name: str, callback: Callable):
        """注册变更监听器"""
        self._listeners[name].append(callback)
    
    def get_all_flags(self) -> Dict[str, Dict]:
        """获取所有特性开关"""
        return {
            name: {
                "status": flag.status.value,
                "description": flag.description,
                "percentage": flag.percentage,
                "user_count": len(flag.user_list),
                "updated_at": flag.updated_at.isoformat()
            }
            for name, flag in self._flags.items()
        }


# ==================== 动态配置 ====================

@dataclass
class ConfigItem(Generic[T]):
    """配置项"""
    key: str
    value: T
    default: T
    description: str = ""
    validator: Optional[Callable[[T], bool]] = None
    transformer: Optional[Callable[[Any], T]] = None
    sensitive: bool = False
    version: int = 1
    updated_at: datetime = field(default_factory=datetime.now)


class DynamicConfig:
    """动态配置管理器"""
    
    def __init__(self, sources: List[ConfigSource] = None):
        self._sources = sources or []
        self._cache: Dict[str, ConfigItem] = {}
        self._defaults: Dict[str, Any] = {}
        self._validators: Dict[str, Callable] = {}
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._refresh_interval = 60
        self._refresh_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    def add_source(self, source: ConfigSource, priority: int = 0):
        """添加配置源"""
        self._sources.insert(priority, source)
    
    def define(
        self,
        key: str,
        default: T,
        description: str = "",
        validator: Callable[[T], bool] = None,
        transformer: Callable[[Any], T] = None,
        sensitive: bool = False
    ):
        """定义配置项"""
        self._defaults[key] = default
        
        if validator:
            self._validators[key] = validator
        
        self._cache[key] = ConfigItem(
            key=key,
            value=default,
            default=default,
            description=description,
            validator=validator,
            transformer=transformer,
            sensitive=sensitive
        )
    
    async def get(self, key: str, default: T = None) -> T:
        """获取配置值"""
        # 从缓存获取
        if key in self._cache:
            return self._cache[key].value
        
        # 从各配置源获取
        for source in self._sources:
            try:
                value = await source.get(key)
                if value is not None:
                    # 验证
                    if key in self._validators:
                        if not self._validators[key](value):
                            logger.warning(f"配置值验证失败: {key}")
                            continue
                    
                    return value
            except Exception as e:
                logger.error(f"从配置源获取失败: {e}")
        
        # 返回默认值
        return self._defaults.get(key, default)
    
    async def set(self, key: str, value: Any, persist: bool = True) -> bool:
        """设置配置值"""
        async with self._lock:
            # 验证
            if key in self._validators:
                if not self._validators[key](value):
                    raise ValueError(f"配置值验证失败: {key}")
            
            old_value = self._cache.get(key, ConfigItem(
                key=key, value=None, default=None
            )).value
            
            # 更新缓存
            if key in self._cache:
                self._cache[key].value = value
                self._cache[key].version += 1
                self._cache[key].updated_at = datetime.now()
            else:
                self._cache[key] = ConfigItem(
                    key=key,
                    value=value,
                    default=value
                )
            
            # 持久化到配置源
            if persist and self._sources:
                try:
                    await self._sources[0].set(key, value)
                except Exception as e:
                    logger.error(f"持久化配置失败: {e}")
            
            # 触发监听器
            if key in self._listeners and old_value != value:
                for listener in self._listeners[key]:
                    try:
                        if asyncio.iscoroutinefunction(listener):
                            await listener(key, old_value, value)
                        else:
                            listener(key, old_value, value)
                    except Exception as e:
                        logger.error(f"配置监听器错误: {e}")
            
            return True
    
    def on_change(self, key: str, callback: Callable):
        """注册配置变更监听器"""
        self._listeners[key].append(callback)
    
    async def refresh(self):
        """刷新所有配置"""
        for key in self._cache:
            value = await self.get(key)
            if value != self._cache[key].value:
                await self.set(key, value, persist=False)
    
    async def start_auto_refresh(self, interval: int = 60):
        """启动自动刷新"""
        self._refresh_interval = interval
        
        async def refresh_loop():
            while True:
                await asyncio.sleep(self._refresh_interval)
                try:
                    await self.refresh()
                except Exception as e:
                    logger.error(f"配置刷新错误: {e}")
        
        self._refresh_task = asyncio.create_task(refresh_loop())
    
    async def stop_auto_refresh(self):
        """停止自动刷新"""
        if self._refresh_task:
            self._refresh_task.cancel()
            self._refresh_task = None
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return {
            key: "***" if item.sensitive else item.value
            for key, item in self._cache.items()
        }


# ==================== 环境管理 ====================

class Environment(str, Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class EnvironmentConfig:
    """环境配置"""
    name: Environment
    variables: Dict[str, Any] = field(default_factory=dict)
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    services: Dict[str, str] = field(default_factory=dict)  # 服务地址


class EnvironmentManager:
    """环境管理器"""
    
    def __init__(self):
        self._current: Environment = Environment.DEVELOPMENT
        self._configs: Dict[Environment, EnvironmentConfig] = {}
        self._detect_environment()
    
    def _detect_environment(self):
        """检测当前环境"""
        env_name = os.environ.get("APP_ENV", "development").lower()
        
        try:
            self._current = Environment(env_name)
        except ValueError:
            self._current = Environment.DEVELOPMENT
        
        logger.info(f"当前环境: {self._current.value}")
    
    @property
    def current(self) -> Environment:
        """当前环境"""
        return self._current
    
    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self._current == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """是否开发环境"""
        return self._current == Environment.DEVELOPMENT
    
    def register(self, config: EnvironmentConfig):
        """注册环境配置"""
        self._configs[config.name] = config
    
    def get_config(self) -> Optional[EnvironmentConfig]:
        """获取当前环境配置"""
        return self._configs.get(self._current)
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取环境变量"""
        config = self.get_config()
        if config and key in config.variables:
            return config.variables[key]
        return os.environ.get(key, default)
    
    def get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务地址"""
        config = self.get_config()
        if config:
            return config.services.get(service_name)
        return None


# ==================== 配置中心统一入口 ====================

class ConfigCenter:
    """配置中心 - 统一配置管理"""
    
    def __init__(self):
        self.environment = EnvironmentManager()
        self.config = DynamicConfig()
        self.features = FeatureFlagManager()
        self._initialized = False
    
    async def initialize(
        self,
        config_file: str = None,
        redis_client: Any = None
    ):
        """初始化配置中心"""
        if self._initialized:
            return
        
        # 添加环境变量源
        self.config.add_source(EnvConfigSource("APP_"), priority=0)
        
        # 添加文件源
        if config_file:
            self.config.add_source(
                FileConfigSource(config_file, auto_reload=True),
                priority=1
            )
        
        # 添加Redis源
        if redis_client:
            self.config.add_source(
                RedisConfigSource(redis_client),
                priority=2
            )
            self.features._config_source = RedisConfigSource(redis_client, prefix="ff:")
        
        # 加载特性开关
        await self.features.load_from_source()
        
        # 定义默认配置
        self._define_defaults()
        
        # 启动自动刷新
        await self.config.start_auto_refresh(60)
        
        self._initialized = True
        logger.info("配置中心初始化完成")
    
    def _define_defaults(self):
        """定义默认配置"""
        # 数据库
        self.config.define("database.pool_size", 20, "数据库连接池大小")
        self.config.define("database.max_overflow", 10, "最大溢出连接")
        self.config.define("database.pool_timeout", 30, "连接超时(秒)")
        
        # 缓存
        self.config.define("cache.default_ttl", 3600, "默认缓存TTL(秒)")
        self.config.define("cache.max_size", 10000, "最大缓存条目")
        
        # API
        self.config.define("api.rate_limit", 100, "API限流(请求/分钟)")
        self.config.define("api.timeout", 30.0, "API超时(秒)")
        
        # 日志
        self.config.define("log.level", "INFO", "日志级别")
        self.config.define("log.format", "json", "日志格式")
        
        # AI
        self.config.define("ai.model", "gpt-3.5-turbo", "默认AI模型")
        self.config.define("ai.max_tokens", 2000, "最大Token数")
        self.config.define("ai.temperature", 0.7, "温度参数")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        return await self.config.get(key, default)
    
    async def set(self, key: str, value: Any) -> bool:
        """设置配置"""
        return await self.config.set(key, value)
    
    def is_feature_enabled(self, name: str, user_id: str = None) -> bool:
        """检查特性是否启用"""
        return self.features.is_enabled(name, user_id)
    
    def get_status(self) -> Dict[str, Any]:
        """获取配置中心状态"""
        return {
            "environment": self.environment.current.value,
            "is_production": self.environment.is_production,
            "config_count": len(self.config._cache),
            "feature_count": len(self.features._flags),
            "initialized": self._initialized
        }


# ==================== 全局实例 ====================

config_center = ConfigCenter()


# ==================== 导出 ====================

__all__ = [
    # 配置源
    "ConfigSource",
    "EnvConfigSource",
    "FileConfigSource",
    "RedisConfigSource",
    # 特性开关
    "FeatureStatus",
    "FeatureFlag",
    "FeatureFlagManager",
    # 动态配置
    "ConfigItem",
    "DynamicConfig",
    # 环境管理
    "Environment",
    "EnvironmentConfig",
    "EnvironmentManager",
    # 配置中心
    "ConfigCenter",
    "config_center",
]
