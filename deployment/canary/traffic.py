# 地方志数据智能管理系统 - 流量管理
"""流量分流和路由"""

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import structlog

logger = structlog.get_logger()


class RouteStrategy(str, Enum):
    """路由策略"""
    RANDOM = "random"           # 随机
    WEIGHTED = "weighted"       # 权重
    HEADER_BASED = "header"     # 基于请求头
    COOKIE_BASED = "cookie"     # 基于Cookie
    USER_BASED = "user"         # 基于用户ID
    IP_BASED = "ip"             # 基于IP


@dataclass
class TrafficRule:
    """流量规则"""
    name: str
    target: str  # 目标版本/服务
    weight: int = 100  # 权重(0-100)
    condition: Optional[Dict[str, Any]] = None  # 匹配条件
    priority: int = 0  # 优先级
    enabled: bool = True
    
    def matches(self, context: Dict[str, Any]) -> bool:
        """检查是否匹配条件"""
        if not self.condition:
            return True
        
        for key, expected in self.condition.items():
            actual = context.get(key)
            
            # 支持多种匹配方式
            if isinstance(expected, dict):
                # 复杂条件
                if "in" in expected:
                    if actual not in expected["in"]:
                        return False
                if "not_in" in expected:
                    if actual in expected["not_in"]:
                        return False
                if "regex" in expected:
                    import re
                    if not re.match(expected["regex"], str(actual)):
                        return False
                if "prefix" in expected:
                    if not str(actual).startswith(expected["prefix"]):
                        return False
            else:
                # 简单相等匹配
                if actual != expected:
                    return False
        
        return True


@dataclass
class WeightedRouting:
    """权重路由"""
    targets: List[tuple]  # [(target, weight), ...]
    
    def select(self) -> str:
        """根据权重选择目标"""
        total_weight = sum(w for _, w in self.targets)
        if total_weight == 0:
            return self.targets[0][0] if self.targets else ""
        
        r = random.randint(1, total_weight)
        cumulative = 0
        
        for target, weight in self.targets:
            cumulative += weight
            if r <= cumulative:
                return target
        
        return self.targets[-1][0]


class TrafficSplitter:
    """流量分流器"""
    
    def __init__(self, strategy: RouteStrategy = RouteStrategy.WEIGHTED):
        self.strategy = strategy
        self.rules: List[TrafficRule] = []
        self.default_target = "stable"
        
        # 统计
        self._stats: Dict[str, int] = {}
        
        # 白名单/黑名单
        self._whitelist: Set[str] = set()  # 用户ID白名单
        self._blacklist: Set[str] = set()  # 用户ID黑名单
    
    def add_rule(self, rule: TrafficRule):
        """添加规则"""
        self.rules.append(rule)
        # 按优先级排序
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info("添加流量规则", name=rule.name, target=rule.target, weight=rule.weight)
    
    def remove_rule(self, name: str):
        """移除规则"""
        self.rules = [r for r in self.rules if r.name != name]
        logger.info("移除流量规则", name=name)
    
    def add_to_whitelist(self, user_id: str):
        """添加到白名单"""
        self._whitelist.add(user_id)
    
    def add_to_blacklist(self, user_id: str):
        """添加到黑名单"""
        self._blacklist.add(user_id)
    
    def route(self, context: Dict[str, Any]) -> str:
        """路由请求"""
        user_id = context.get("user_id", "")
        
        # 检查白名单（直接使用新版本）
        if user_id in self._whitelist:
            return "canary"
        
        # 检查黑名单（使用稳定版本）
        if user_id in self._blacklist:
            return "stable"
        
        # 应用策略
        if self.strategy == RouteStrategy.RANDOM:
            target = self._route_random()
        elif self.strategy == RouteStrategy.WEIGHTED:
            target = self._route_weighted(context)
        elif self.strategy == RouteStrategy.HEADER_BASED:
            target = self._route_by_header(context)
        elif self.strategy == RouteStrategy.COOKIE_BASED:
            target = self._route_by_cookie(context)
        elif self.strategy == RouteStrategy.USER_BASED:
            target = self._route_by_user(context)
        elif self.strategy == RouteStrategy.IP_BASED:
            target = self._route_by_ip(context)
        else:
            target = self.default_target
        
        # 统计
        self._stats[target] = self._stats.get(target, 0) + 1
        
        return target
    
    def _route_random(self) -> str:
        """随机路由"""
        enabled_rules = [r for r in self.rules if r.enabled]
        if not enabled_rules:
            return self.default_target
        
        weights = [(r.target, r.weight) for r in enabled_rules]
        return WeightedRouting(weights).select()
    
    def _route_weighted(self, context: Dict[str, Any]) -> str:
        """权重路由"""
        # 首先检查条件匹配
        for rule in self.rules:
            if rule.enabled and rule.matches(context):
                # 按权重决定是否命中
                if random.randint(1, 100) <= rule.weight:
                    return rule.target
        
        return self.default_target
    
    def _route_by_header(self, context: Dict[str, Any]) -> str:
        """基于请求头路由"""
        headers = context.get("headers", {})
        
        # 检查特定的路由头
        route_header = headers.get("X-Route-To")
        if route_header:
            return route_header
        
        # 检查规则
        for rule in self.rules:
            if rule.enabled and rule.condition:
                header_conditions = {k: v for k, v in rule.condition.items() if k.startswith("header_")}
                if all(headers.get(k[7:]) == v for k, v in header_conditions.items()):
                    return rule.target
        
        return self.default_target
    
    def _route_by_cookie(self, context: Dict[str, Any]) -> str:
        """基于Cookie路由"""
        cookies = context.get("cookies", {})
        
        # 检查灰度Cookie
        canary_cookie = cookies.get("canary")
        if canary_cookie == "true":
            return "canary"
        
        return self.default_target
    
    def _route_by_user(self, context: Dict[str, Any]) -> str:
        """基于用户ID路由（一致性哈希）"""
        user_id = context.get("user_id", "")
        if not user_id:
            return self.default_target
        
        # 一致性哈希
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
        
        cumulative = 0
        for rule in self.rules:
            if rule.enabled:
                cumulative += rule.weight
                if hash_value < cumulative:
                    return rule.target
        
        return self.default_target
    
    def _route_by_ip(self, context: Dict[str, Any]) -> str:
        """基于IP路由"""
        client_ip = context.get("client_ip", "")
        if not client_ip:
            return self.default_target
        
        # IP哈希
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16) % 100
        
        cumulative = 0
        for rule in self.rules:
            if rule.enabled:
                cumulative += rule.weight
                if hash_value < cumulative:
                    return rule.target
        
        return self.default_target
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = sum(self._stats.values())
        return {
            "total_requests": total,
            "by_target": dict(self._stats),
            "percentages": {
                k: f"{v/total*100:.1f}%" if total > 0 else "0%"
                for k, v in self._stats.items()
            }
        }
    
    def reset_stats(self):
        """重置统计"""
        self._stats.clear()


# FastAPI中间件
class TrafficSplitterMiddleware:
    """流量分流中间件"""
    
    def __init__(self, app, splitter: TrafficSplitter):
        self.app = app
        self.splitter = splitter
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        # 构建路由上下文
        from starlette.requests import Request
        request = Request(scope, receive)
        
        context = {
            "user_id": request.headers.get("X-User-ID", ""),
            "client_ip": request.client.host if request.client else "",
            "headers": dict(request.headers),
            "cookies": request.cookies,
            "path": str(request.url.path),
            "method": request.method,
        }
        
        # 路由决策
        target = self.splitter.route(context)
        
        # 添加响应头标识
        scope["state"]["route_target"] = target
        
        return await self.app(scope, receive, send)
