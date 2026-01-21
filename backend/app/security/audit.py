# 地方志数据智能管理系统 - 安全审计模块
"""安全事件记录和审计追踪"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger()


class AuditEventType(str, Enum):
    """审计事件类型"""
    # 认证相关
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # 授权相关
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"
    ROLE_CHANGE = "role_change"
    
    # 数据操作
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    
    # 系统事件
    CONFIG_CHANGE = "config_change"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    BACKUP_CREATED = "backup_created"
    
    # 安全事件
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """审计事件"""
    id: str
    event_type: AuditEventType
    timestamp: datetime
    actor_id: Optional[int]        # 操作者ID
    actor_type: str                # user/service/system
    resource_type: str             # 资源类型
    resource_id: Optional[str]     # 资源ID
    action: str                    # 动作描述
    outcome: str                   # success/failure
    risk_level: RiskLevel
    ip_address: str = ""
    user_agent: str = ""
    request_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "outcome": self.outcome,
            "risk_level": self.risk_level.value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "details": self.details
        }


class SecurityAuditor:
    """安全审计器"""
    
    def __init__(self, storage_path: str = "data/audit"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.events: List[AuditEvent] = []
        self._callbacks: List[Callable[[AuditEvent], None]] = []
    
    def on_event(self, callback: Callable[[AuditEvent], None]):
        """注册事件回调"""
        self._callbacks.append(callback)
    
    def log_event(self, event: AuditEvent):
        """记录审计事件"""
        self.events.append(event)
        
        # 持久化
        self._persist_event(event)
        
        # 日志
        log_method = logger.info
        if event.risk_level == RiskLevel.HIGH:
            log_method = logger.warning
        elif event.risk_level == RiskLevel.CRITICAL:
            log_method = logger.error
        
        log_method(
            "审计事件",
            event_type=event.event_type.value,
            actor_id=event.actor_id,
            resource=f"{event.resource_type}/{event.resource_id}",
            outcome=event.outcome,
            risk=event.risk_level.value
        )
        
        # 触发回调
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error("审计回调失败", error=str(e))
    
    def _persist_event(self, event: AuditEvent):
        """持久化事件"""
        date_str = event.timestamp.strftime("%Y-%m-%d")
        file_path = self.storage_path / f"audit_{date_str}.jsonl"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    
    def log_authentication(
        self,
        user_id: Optional[int],
        success: bool,
        ip_address: str,
        user_agent: str = "",
        failure_reason: str = ""
    ):
        """记录认证事件"""
        event = AuditEvent(
            id=f"auth_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED,
            timestamp=datetime.now(),
            actor_id=user_id,
            actor_type="user",
            resource_type="authentication",
            resource_id=None,
            action="login",
            outcome="success" if success else "failure",
            risk_level=RiskLevel.LOW if success else RiskLevel.MEDIUM,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"failure_reason": failure_reason} if failure_reason else {}
        )
        self.log_event(event)
    
    def log_data_access(
        self,
        user_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str = ""
    ):
        """记录数据访问"""
        event_type_map = {
            "create": AuditEventType.DATA_CREATE,
            "read": AuditEventType.DATA_READ,
            "update": AuditEventType.DATA_UPDATE,
            "delete": AuditEventType.DATA_DELETE,
            "export": AuditEventType.DATA_EXPORT,
        }
        
        event = AuditEvent(
            id=f"data_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            event_type=event_type_map.get(action, AuditEventType.DATA_READ),
            timestamp=datetime.now(),
            actor_id=user_id,
            actor_type="user",
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome="success",
            risk_level=RiskLevel.LOW,
            ip_address=ip_address
        )
        self.log_event(event)
    
    def log_security_event(
        self,
        event_type: AuditEventType,
        description: str,
        risk_level: RiskLevel,
        details: Dict = None,
        ip_address: str = ""
    ):
        """记录安全事件"""
        event = AuditEvent(
            id=f"sec_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            event_type=event_type,
            timestamp=datetime.now(),
            actor_id=None,
            actor_type="system",
            resource_type="security",
            resource_id=None,
            action=description,
            outcome="detected",
            risk_level=risk_level,
            ip_address=ip_address,
            details=details or {}
        )
        self.log_event(event)
    
    def query_events(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        event_types: List[AuditEventType] = None,
        actor_id: int = None,
        risk_levels: List[RiskLevel] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """查询审计事件"""
        results = []
        
        for event in reversed(self.events):  # 最新的在前
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if event_types and event.event_type not in event_types:
                continue
            if actor_id and event.actor_id != actor_id:
                continue
            if risk_levels and event.risk_level not in risk_levels:
                continue
            
            results.append(event)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取安全摘要"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent_events = [e for e in self.events if e.timestamp > cutoff]
        
        # 统计
        by_type = {}
        by_risk = {}
        failed_logins = 0
        suspicious_ips = set()
        
        for event in recent_events:
            by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
            by_risk[event.risk_level.value] = by_risk.get(event.risk_level.value, 0) + 1
            
            if event.event_type == AuditEventType.LOGIN_FAILED:
                failed_logins += 1
            
            if event.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                if event.ip_address:
                    suspicious_ips.add(event.ip_address)
        
        return {
            "period_hours": hours,
            "total_events": len(recent_events),
            "by_type": by_type,
            "by_risk": by_risk,
            "failed_logins": failed_logins,
            "suspicious_ips": list(suspicious_ips),
            "high_risk_events": by_risk.get("high", 0) + by_risk.get("critical", 0)
        }


class BruteForceDetector:
    """暴力破解检测"""
    
    def __init__(
        self,
        max_attempts: int = 5,
        window_minutes: int = 15,
        auditor: SecurityAuditor = None
    ):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.auditor = auditor
        self.attempts: Dict[str, List[datetime]] = {}  # IP -> 尝试时间列表
    
    def record_attempt(self, ip_address: str, success: bool) -> bool:
        """记录尝试，返回是否应该阻止"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=self.window_minutes)
        
        if ip_address not in self.attempts:
            self.attempts[ip_address] = []
        
        # 清理过期记录
        self.attempts[ip_address] = [
            t for t in self.attempts[ip_address] if t > cutoff
        ]
        
        if not success:
            self.attempts[ip_address].append(now)
        
        # 检查是否超过阈值
        if len(self.attempts[ip_address]) >= self.max_attempts:
            if self.auditor:
                self.auditor.log_security_event(
                    AuditEventType.BRUTE_FORCE_DETECTED,
                    f"检测到暴力破解: {ip_address}",
                    RiskLevel.HIGH,
                    {"attempts": len(self.attempts[ip_address])},
                    ip_address
                )
            return True
        
        return False
    
    def is_blocked(self, ip_address: str) -> bool:
        """检查IP是否被阻止"""
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        
        if ip_address not in self.attempts:
            return False
        
        recent = [t for t in self.attempts[ip_address] if t > cutoff]
        return len(recent) >= self.max_attempts


# FastAPI中间件
class AuditMiddleware:
    """审计中间件"""
    
    def __init__(self, app, auditor: SecurityAuditor):
        self.app = app
        self.auditor = auditor
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        from starlette.requests import Request
        request = Request(scope, receive)
        
        # 记录请求
        user_id = scope.get("state", {}).get("user_id")
        ip_address = request.client.host if request.client else ""
        
        # 这里可以根据路径判断是否需要审计
        # 例如敏感操作自动记录
        
        return await self.app(scope, receive, send)
