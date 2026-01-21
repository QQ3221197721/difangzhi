# 地方志数据智能管理系统 - 缓存配置
"""Redis缓存配置"""

from typing import Optional
from datetime import timedelta

# 缓存配置
CACHE_CONFIG = {
    # Redis连接
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
        "max_connections": 20,
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
    },
    
    # 缓存键前缀
    "key_prefix": "lcs:",
    
    # 默认过期时间(秒)
    "default_ttl": 3600,
}

# 缓存策略
CACHE_POLICIES = {
    # 文档缓存
    "document": {
        "prefix": "doc:",
        "ttl": 3600,  # 1小时
        "serialize": "json",
    },
    
    # 用户会话缓存
    "session": {
        "prefix": "session:",
        "ttl": 86400,  # 24小时
        "serialize": "json",
    },
    
    # 搜索结果缓存
    "search": {
        "prefix": "search:",
        "ttl": 600,  # 10分钟
        "serialize": "json",
    },
    
    # AI响应缓存
    "ai_response": {
        "prefix": "ai:",
        "ttl": 1800,  # 30分钟
        "serialize": "json",
    },
    
    # 向量缓存
    "embedding": {
        "prefix": "emb:",
        "ttl": 86400,  # 24小时
        "serialize": "pickle",
    },
    
    # 统计数据缓存
    "stats": {
        "prefix": "stats:",
        "ttl": 300,  # 5分钟
        "serialize": "json",
    },
}

# 缓存键生成器
def make_cache_key(policy: str, *args, **kwargs) -> str:
    """
    生成缓存键
    
    Args:
        policy: 缓存策略名称
        *args: 位置参数
        **kwargs: 关键字参数
    
    Returns:
        缓存键字符串
    """
    config = CACHE_POLICIES.get(policy, {})
    prefix = CACHE_CONFIG["key_prefix"] + config.get("prefix", "")
    
    parts = [prefix]
    parts.extend(str(arg) for arg in args)
    parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    
    return ":".join(parts)


def get_ttl(policy: str) -> int:
    """获取缓存过期时间"""
    config = CACHE_POLICIES.get(policy, {})
    return config.get("ttl", CACHE_CONFIG["default_ttl"])
