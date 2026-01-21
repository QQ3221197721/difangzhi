# 地方志数据智能管理系统 - 访问控制
"""RBAC/ABAC、权限策略、零信任架构"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from functools import wraps
import structlog

logger = structlog.get_logger()


class Permission(str, Enum):
    """权限定义"""
    # 文档权限
    DOCUMENT_CREATE = "document:create"
    DOCUMENT_READ = "document:read"
    DOCUMENT_UPDATE = "document:update"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_EXPORT = "document:export"
    
    # 用户管理
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # 系统管理
    SYSTEM_CONFIG = "system:config"
    SYSTEM_AUDIT = "system:audit"
    SYSTEM_BACKUP = "system:backup"
    
    # AI功能
    AI_CHAT = "ai:chat"
    AI_ANALYZE = "ai:analyze"
    AI_ADMIN = "ai:admin"
    
    # 管理权限
    ADMIN_FULL = "admin:*"


class ResourceType(str, Enum):
    """资源类型"""
    DOCUMENT = "document"
    USER = "user"
    SYSTEM = "system"
    AI = "ai"
    REPORT = "report"


@dataclass
class Role:
    """角色"""
    id: str
    name: str
    description: str
    permissions: Set[Permission]
    is_system: bool = False  # 系统内置角色
    created_at: datetime = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()
    
    def has_permission(self, permission: Permission) -> bool:
        if Permission.ADMIN_FULL in self.permissions:
            return True
        return permission in self.permissions
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "is_system": self.is_system
        }


@dataclass
class Policy:
    """访问策略(ABAC)"""
    id: str
    name: str
    effect: str  # allow/deny
    resources: List[str]  # 资源模式
    actions: List[str]    # 动作
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0     # 优先级，数字越大优先级越高
    
    def matches(
        self,
        resource: str,
        action: str,
        context: Dict[str, Any]
    ) -> bool:
        """检查策略是否匹配"""
        # 检查资源
        resource_match = any(
            self._pattern_match(pattern, resource)
            for pattern in self.resources
        )
        if not resource_match:
            return False
        
        # 检查动作
        action_match = action in self.actions or "*" in self.actions
        if not action_match:
            return False
        
        # 检查条件
        return self._evaluate_conditions(context)
    
    def _pattern_match(self, pattern: str, value: str) -> bool:
        """模式匹配（支持通配符）"""
        if pattern == "*":
            return True
        
        if pattern.endswith("*"):
            return value.startswith(pattern[:-1])
        
        return pattern == value
    
    def _evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """评估条件"""
        for key, condition in self.conditions.items():
            ctx_value = context.get(key)
            
            if isinstance(condition, dict):
                # 复杂条件
                op = condition.get("op", "eq")
                value = condition.get("value")
                
                if op == "eq" and ctx_value != value:
                    return False
                elif op == "ne" and ctx_value == value:
                    return False
                elif op == "in" and ctx_value not in value:
                    return False
                elif op == "contains" and value not in ctx_value:
                    return False
                elif op == "gt" and not (ctx_value > value):
                    return False
                elif op == "lt" and not (ctx_value < value):
                    return False
            else:
                # 简单相等条件
                if ctx_value != condition:
                    return False
        
        return True


@dataclass
class AccessRequest:
    """访问请求"""
    subject_id: int       # 主体ID（用户）
    subject_type: str     # 主体类型
    resource: str         # 资源标识
    resource_type: ResourceType
    action: str           # 动作
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class AccessDecision:
    """访问决策"""
    allowed: bool
    reason: str
    matched_policy: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


class RBACManager:
    """基于角色的访问控制管理器"""
    
    # 预定义角色
    SYSTEM_ROLES = {
        "admin": Role(
            id="admin",
            name="系统管理员",
            description="拥有所有权限",
            permissions={Permission.ADMIN_FULL},
            is_system=True
        ),
        "editor": Role(
            id="editor",
            name="编辑",
            description="可以创建和编辑文档",
            permissions={
                Permission.DOCUMENT_CREATE,
                Permission.DOCUMENT_READ,
                Permission.DOCUMENT_UPDATE,
                Permission.AI_CHAT,
                Permission.AI_ANALYZE
            },
            is_system=True
        ),
        "viewer": Role(
            id="viewer",
            name="查看者",
            description="只能查看文档",
            permissions={
                Permission.DOCUMENT_READ,
                Permission.AI_CHAT
            },
            is_system=True
        ),
        "analyst": Role(
            id="analyst",
            name="分析师",
            description="可以使用AI分析功能",
            permissions={
                Permission.DOCUMENT_READ,
                Permission.DOCUMENT_EXPORT,
                Permission.AI_CHAT,
                Permission.AI_ANALYZE
            },
            is_system=True
        )
    }
    
    def __init__(self):
        self.roles: Dict[str, Role] = dict(self.SYSTEM_ROLES)
        self.user_roles: Dict[int, Set[str]] = {}  # user_id -> role_ids
    
    def create_role(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: Set[Permission]
    ) -> Role:
        """创建角色"""
        if role_id in self.roles:
            raise ValueError(f"角色已存在: {role_id}")
        
        role = Role(
            id=role_id,
            name=name,
            description=description,
            permissions=permissions
        )
        self.roles[role_id] = role
        
        logger.info("角色已创建", role_id=role_id)
        return role
    
    def delete_role(self, role_id: str):
        """删除角色"""
        if role_id not in self.roles:
            return
        
        if self.roles[role_id].is_system:
            raise ValueError("不能删除系统角色")
        
        del self.roles[role_id]
        
        # 从用户中移除此角色
        for user_id in self.user_roles:
            self.user_roles[user_id].discard(role_id)
    
    def assign_role(self, user_id: int, role_id: str):
        """为用户分配角色"""
        if role_id not in self.roles:
            raise ValueError(f"角色不存在: {role_id}")
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = set()
        
        self.user_roles[user_id].add(role_id)
        logger.info("角色已分配", user_id=user_id, role_id=role_id)
    
    def revoke_role(self, user_id: int, role_id: str):
        """撤销用户角色"""
        if user_id in self.user_roles:
            self.user_roles[user_id].discard(role_id)
    
    def get_user_roles(self, user_id: int) -> List[Role]:
        """获取用户角色"""
        role_ids = self.user_roles.get(user_id, set())
        return [self.roles[rid] for rid in role_ids if rid in self.roles]
    
    def get_user_permissions(self, user_id: int) -> Set[Permission]:
        """获取用户所有权限"""
        permissions = set()
        for role in self.get_user_roles(user_id):
            permissions.update(role.permissions)
        return permissions
    
    def check_permission(self, user_id: int, permission: Permission) -> bool:
        """检查用户是否有权限"""
        permissions = self.get_user_permissions(user_id)
        
        if Permission.ADMIN_FULL in permissions:
            return True
        
        return permission in permissions


class ABACManager:
    """基于属性的访问控制管理器"""
    
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
    
    def add_policy(self, policy: Policy):
        """添加策略"""
        self.policies[policy.id] = policy
        logger.info("策略已添加", policy_id=policy.id)
    
    def remove_policy(self, policy_id: str):
        """移除策略"""
        self.policies.pop(policy_id, None)
    
    def evaluate(
        self,
        resource: str,
        action: str,
        context: Dict[str, Any]
    ) -> AccessDecision:
        """评估访问请求"""
        # 按优先级排序策略
        sorted_policies = sorted(
            self.policies.values(),
            key=lambda p: p.priority,
            reverse=True
        )
        
        for policy in sorted_policies:
            if policy.matches(resource, action, context):
                allowed = policy.effect == "allow"
                return AccessDecision(
                    allowed=allowed,
                    reason=f"匹配策略: {policy.name}",
                    matched_policy=policy.id
                )
        
        # 默认拒绝
        return AccessDecision(
            allowed=False,
            reason="没有匹配的策略，默认拒绝"
        )


class ZeroTrustManager:
    """零信任架构管理器"""
    
    def __init__(self):
        self.device_registry: Dict[str, Dict[str, Any]] = {}
        self.session_scores: Dict[str, float] = {}  # session_id -> trust_score
        self.risk_factors: Dict[str, float] = {
            "unknown_device": -0.3,
            "unusual_location": -0.2,
            "unusual_time": -0.1,
            "failed_mfa": -0.4,
            "weak_authentication": -0.2,
            "verified_device": 0.2,
            "strong_authentication": 0.3,
            "normal_behavior": 0.1
        }
        self.min_trust_score = 0.5
    
    def register_device(
        self,
        device_id: str,
        user_id: int,
        device_info: Dict[str, Any]
    ):
        """注册设备"""
        self.device_registry[device_id] = {
            "user_id": user_id,
            "device_info": device_info,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "trusted": False
        }
    
    def verify_device(self, device_id: str):
        """验证设备"""
        if device_id in self.device_registry:
            self.device_registry[device_id]["trusted"] = True
    
    def calculate_trust_score(
        self,
        session_id: str,
        user_id: int,
        context: Dict[str, Any]
    ) -> float:
        """计算信任分数"""
        score = 0.5  # 基础分
        
        # 设备因素
        device_id = context.get("device_id")
        if device_id:
            if device_id in self.device_registry:
                device = self.device_registry[device_id]
                if device["trusted"]:
                    score += self.risk_factors["verified_device"]
            else:
                score += self.risk_factors["unknown_device"]
        
        # 位置因素
        if context.get("unusual_location"):
            score += self.risk_factors["unusual_location"]
        
        # 时间因素
        hour = datetime.now().hour
        if hour < 6 or hour > 22:  # 非正常工作时间
            score += self.risk_factors["unusual_time"]
        
        # 认证因素
        auth_method = context.get("auth_method", "password")
        if auth_method in ["mfa", "biometric", "hardware_key"]:
            score += self.risk_factors["strong_authentication"]
        elif auth_method == "password":
            score += self.risk_factors["weak_authentication"]
        
        # 行为因素
        if context.get("normal_behavior"):
            score += self.risk_factors["normal_behavior"]
        
        # 限制范围
        score = max(0.0, min(1.0, score))
        
        self.session_scores[session_id] = score
        return score
    
    def should_challenge(self, session_id: str) -> bool:
        """是否需要额外验证"""
        score = self.session_scores.get(session_id, 0.5)
        return score < self.min_trust_score
    
    def should_allow(
        self,
        session_id: str,
        resource_sensitivity: str = "normal"
    ) -> bool:
        """是否允许访问"""
        score = self.session_scores.get(session_id, 0.5)
        
        sensitivity_thresholds = {
            "low": 0.3,
            "normal": 0.5,
            "high": 0.7,
            "critical": 0.9
        }
        
        threshold = sensitivity_thresholds.get(resource_sensitivity, 0.5)
        return score >= threshold


class AccessControlManager:
    """综合访问控制管理器"""
    
    def __init__(self):
        self.rbac = RBACManager()
        self.abac = ABACManager()
        self.zero_trust = ZeroTrustManager()
        
        self._access_log: List[Dict[str, Any]] = []
    
    async def check_access(
        self,
        request: AccessRequest
    ) -> AccessDecision:
        """检查访问权限"""
        # 1. RBAC检查
        permission = self._get_permission_for_action(
            request.resource_type,
            request.action
        )
        
        if permission:
            if not self.rbac.check_permission(request.subject_id, permission):
                decision = AccessDecision(
                    allowed=False,
                    reason=f"RBAC: 缺少权限 {permission.value}"
                )
                self._log_access(request, decision)
                return decision
        
        # 2. ABAC检查
        abac_decision = self.abac.evaluate(
            request.resource,
            request.action,
            {
                "user_id": request.subject_id,
                "resource_type": request.resource_type.value,
                **request.context
            }
        )
        
        if not abac_decision.allowed:
            self._log_access(request, abac_decision)
            return abac_decision
        
        # 3. 零信任检查
        session_id = request.context.get("session_id")
        if session_id:
            sensitivity = self._get_resource_sensitivity(request.resource_type)
            
            if not self.zero_trust.should_allow(session_id, sensitivity):
                if self.zero_trust.should_challenge(session_id):
                    decision = AccessDecision(
                        allowed=False,
                        reason="Zero Trust: 需要额外验证"
                    )
                else:
                    decision = AccessDecision(
                        allowed=False,
                        reason="Zero Trust: 信任分数不足"
                    )
                self._log_access(request, decision)
                return decision
        
        # 允许访问
        decision = AccessDecision(
            allowed=True,
            reason="通过所有访问检查"
        )
        self._log_access(request, decision)
        return decision
    
    def _get_permission_for_action(
        self,
        resource_type: ResourceType,
        action: str
    ) -> Optional[Permission]:
        """获取动作对应的权限"""
        permission_map = {
            (ResourceType.DOCUMENT, "create"): Permission.DOCUMENT_CREATE,
            (ResourceType.DOCUMENT, "read"): Permission.DOCUMENT_READ,
            (ResourceType.DOCUMENT, "update"): Permission.DOCUMENT_UPDATE,
            (ResourceType.DOCUMENT, "delete"): Permission.DOCUMENT_DELETE,
            (ResourceType.DOCUMENT, "export"): Permission.DOCUMENT_EXPORT,
            (ResourceType.USER, "create"): Permission.USER_CREATE,
            (ResourceType.USER, "read"): Permission.USER_READ,
            (ResourceType.USER, "update"): Permission.USER_UPDATE,
            (ResourceType.USER, "delete"): Permission.USER_DELETE,
            (ResourceType.AI, "chat"): Permission.AI_CHAT,
            (ResourceType.AI, "analyze"): Permission.AI_ANALYZE,
            (ResourceType.SYSTEM, "config"): Permission.SYSTEM_CONFIG,
        }
        
        return permission_map.get((resource_type, action))
    
    def _get_resource_sensitivity(self, resource_type: ResourceType) -> str:
        """获取资源敏感度"""
        sensitivity_map = {
            ResourceType.DOCUMENT: "normal",
            ResourceType.USER: "high",
            ResourceType.SYSTEM: "critical",
            ResourceType.AI: "normal",
            ResourceType.REPORT: "high"
        }
        return sensitivity_map.get(resource_type, "normal")
    
    def _log_access(self, request: AccessRequest, decision: AccessDecision):
        """记录访问日志"""
        self._access_log.append({
            "timestamp": datetime.now().isoformat(),
            "subject_id": request.subject_id,
            "resource": request.resource,
            "action": request.action,
            "allowed": decision.allowed,
            "reason": decision.reason
        })
        
        if not decision.allowed:
            logger.warning(
                "访问被拒绝",
                user_id=request.subject_id,
                resource=request.resource,
                action=request.action,
                reason=decision.reason
            )


# 装饰器
def require_permission(permission: Permission):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从上下文获取用户ID（需要与框架集成）
            user_id = kwargs.get("current_user_id")
            if user_id is None:
                raise PermissionError("未认证")
            
            # 检查权限
            # 这里需要访问控制管理器实例
            # 实际使用时应该通过依赖注入
            rbac = RBACManager()
            if not rbac.check_permission(user_id, permission):
                raise PermissionError(f"缺少权限: {permission.value}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_roles(*role_ids: str):
    """角色检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get("current_user_id")
            if user_id is None:
                raise PermissionError("未认证")
            
            rbac = RBACManager()
            user_roles = {r.id for r in rbac.get_user_roles(user_id)}
            
            if not any(rid in user_roles for rid in role_ids):
                raise PermissionError(f"需要角色: {role_ids}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
