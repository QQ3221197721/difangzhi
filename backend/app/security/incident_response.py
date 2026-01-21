"""
事件响应模块 - 安全事件处理、告警、SOAR
Incident Response Module - Security Incident Handling, Alerting, SOAR
"""

import asyncio
import hashlib
import json
import smtplib
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import logging
import threading

logger = logging.getLogger(__name__)


# ==================== 事件类型定义 ====================

class IncidentSeverity(str, Enum):
    """事件严重程度"""
    P1_CRITICAL = "P1"   # 关键 - 立即响应
    P2_HIGH = "P2"       # 高 - 1小时内响应
    P3_MEDIUM = "P3"     # 中 - 4小时内响应
    P4_LOW = "P4"        # 低 - 24小时内响应
    P5_INFO = "P5"       # 信息 - 按需处理


class IncidentStatus(str, Enum):
    """事件状态"""
    NEW = "new"                    # 新建
    ACKNOWLEDGED = "acknowledged"  # 已确认
    INVESTIGATING = "investigating"  # 调查中
    CONTAINMENT = "containment"    # 遏制中
    ERADICATION = "eradication"    # 根除中
    RECOVERY = "recovery"          # 恢复中
    RESOLVED = "resolved"          # 已解决
    CLOSED = "closed"              # 已关闭
    FALSE_POSITIVE = "false_positive"  # 误报


class IncidentCategory(str, Enum):
    """事件类别"""
    MALWARE = "malware"            # 恶意软件
    INTRUSION = "intrusion"        # 入侵
    DATA_BREACH = "data_breach"    # 数据泄露
    DOS = "dos"                    # 拒绝服务
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 未授权访问
    PHISHING = "phishing"          # 钓鱼攻击
    INSIDER_THREAT = "insider_threat"  # 内部威胁
    VULNERABILITY = "vulnerability"  # 漏洞利用
    POLICY_VIOLATION = "policy_violation"  # 策略违规
    SUSPICIOUS_ACTIVITY = "suspicious_activity"  # 可疑活动
    OTHER = "other"


class AlertChannel(str, Enum):
    """告警通道"""
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    DINGTALK = "dingtalk"
    WECHAT = "wechat"


# ==================== 数据模型 ====================

@dataclass
class IncidentEvent:
    """事件记录"""
    id: str
    timestamp: datetime
    actor: str
    action: str
    details: str
    attachments: List[str] = field(default_factory=list)


@dataclass
class Incident:
    """安全事件"""
    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    category: IncidentCategory
    source: str
    created_at: datetime
    updated_at: datetime
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    affected_assets: List[str] = field(default_factory=list)
    indicators: List[str] = field(default_factory=list)
    timeline: List[IncidentEvent] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    playbook_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "category": self.category.value,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "assigned_to": self.assigned_to,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "tags": self.tags,
            "affected_assets": self.affected_assets,
            "indicators": self.indicators,
            "timeline": [{"id": e.id, "timestamp": e.timestamp.isoformat(), 
                         "actor": e.actor, "action": e.action, "details": e.details}
                        for e in self.timeline],
            "related_incidents": self.related_incidents,
            "playbook_id": self.playbook_id,
            "metadata": self.metadata
        }
    
    def add_event(self, actor: str, action: str, details: str):
        """添加事件记录"""
        event = IncidentEvent(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            actor=actor,
            action=action,
            details=details
        )
        self.timeline.append(event)
        self.updated_at = datetime.now()


@dataclass
class Alert:
    """告警"""
    id: str
    title: str
    message: str
    severity: IncidentSeverity
    source: str
    channels: List[AlertChannel]
    created_at: datetime
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    incident_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== 告警通知器 ====================

class AlertNotifier(ABC):
    """告警通知器基类"""
    
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """发送告警"""
        pass


class EmailNotifier(AlertNotifier):
    """邮件通知器"""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str]
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
    
    async def send(self, alert: Alert) -> bool:
        """发送邮件告警"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)
            msg['Subject'] = f"[{alert.severity.value}] {alert.title}"
            
            body = f"""
            安全告警通知
            ============
            
            告警ID: {alert.id}
            严重程度: {alert.severity.value}
            来源: {alert.source}
            时间: {alert.created_at.isoformat()}
            
            详情:
            {alert.message}
            
            ---
            此邮件由安全监控系统自动发送
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 异步发送
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email, msg)
            
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def _send_email(self, msg):
        """同步发送邮件"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)


class WebhookNotifier(AlertNotifier):
    """Webhook通知器"""
    
    def __init__(self, webhook_url: str, headers: Optional[Dict[str, str]] = None):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}
    
    async def send(self, alert: Alert) -> bool:
        """发送Webhook通知"""
        try:
            import aiohttp
            
            payload = {
                "alert_id": alert.id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "source": alert.source,
                "timestamp": alert.created_at.isoformat(),
                "metadata": alert.metadata
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=10
                ) as response:
                    return response.status < 400
        except Exception as e:
            logger.error(f"Webhook发送失败: {e}")
            return False


class DingTalkNotifier(AlertNotifier):
    """钉钉通知器"""
    
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret
    
    async def send(self, alert: Alert) -> bool:
        """发送钉钉通知"""
        try:
            import aiohttp
            import hmac
            import base64
            import urllib.parse
            
            url = self.webhook_url
            
            # 签名
            if self.secret:
                timestamp = str(round(datetime.now().timestamp() * 1000))
                secret_enc = self.secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{self.secret}'
                hmac_code = hmac.new(
                    secret_enc,
                    string_to_sign.encode('utf-8'),
                    digestmod='sha256'
                ).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            
            # 消息内容
            color_map = {
                IncidentSeverity.P1_CRITICAL: "#FF0000",
                IncidentSeverity.P2_HIGH: "#FF6600",
                IncidentSeverity.P3_MEDIUM: "#FFCC00",
                IncidentSeverity.P4_LOW: "#00CC00",
                IncidentSeverity.P5_INFO: "#0099FF",
            }
            
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"[{alert.severity.value}] {alert.title}",
                    "text": f"""### 安全告警 [{alert.severity.value}]
                    
**{alert.title}**

- 告警ID: {alert.id}
- 来源: {alert.source}
- 时间: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}

**详情:**
{alert.message}
"""
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"钉钉通知发送失败: {e}")
            return False


class SlackNotifier(AlertNotifier):
    """Slack通知器"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, alert: Alert) -> bool:
        """发送Slack通知"""
        try:
            import aiohttp
            
            color_map = {
                IncidentSeverity.P1_CRITICAL: "danger",
                IncidentSeverity.P2_HIGH: "danger",
                IncidentSeverity.P3_MEDIUM: "warning",
                IncidentSeverity.P4_LOW: "good",
                IncidentSeverity.P5_INFO: "#0099FF",
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "warning"),
                    "title": f"[{alert.severity.value}] {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "告警ID", "value": alert.id, "short": True},
                        {"title": "来源", "value": alert.source, "short": True},
                        {"title": "时间", "value": alert.created_at.strftime('%Y-%m-%d %H:%M:%S'), "short": True},
                    ],
                    "footer": "安全监控系统"
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Slack通知发送失败: {e}")
            return False


# ==================== 告警管理器 ====================

class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.notifiers: Dict[AlertChannel, AlertNotifier] = {}
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules: List[Dict] = []
        self.suppression_rules: List[Dict] = []
        self._alert_counts: Dict[str, int] = defaultdict(int)
    
    def register_notifier(self, channel: AlertChannel, notifier: AlertNotifier):
        """注册通知器"""
        self.notifiers[channel] = notifier
    
    def add_alert_rule(
        self,
        name: str,
        condition: Callable[[Dict], bool],
        severity: IncidentSeverity,
        channels: List[AlertChannel],
        message_template: str
    ):
        """添加告警规则"""
        self.alert_rules.append({
            "name": name,
            "condition": condition,
            "severity": severity,
            "channels": channels,
            "message_template": message_template
        })
    
    def add_suppression_rule(
        self,
        name: str,
        condition: Callable[[Alert], bool],
        duration: timedelta
    ):
        """添加抑制规则"""
        self.suppression_rules.append({
            "name": name,
            "condition": condition,
            "duration": duration,
            "last_triggered": {}
        })
    
    async def process_event(self, event: Dict[str, Any]) -> Optional[Alert]:
        """处理事件，触发告警"""
        for rule in self.alert_rules:
            if rule["condition"](event):
                alert = Alert(
                    id=str(uuid.uuid4())[:12],
                    title=rule["name"],
                    message=rule["message_template"].format(**event),
                    severity=rule["severity"],
                    source=event.get("source", "unknown"),
                    channels=rule["channels"],
                    created_at=datetime.now(),
                    metadata=event
                )
                
                # 检查抑制规则
                if not self._should_suppress(alert):
                    await self.send_alert(alert)
                    return alert
        
        return None
    
    def _should_suppress(self, alert: Alert) -> bool:
        """检查是否应抑制告警"""
        for rule in self.suppression_rules:
            if rule["condition"](alert):
                key = f"{rule['name']}:{alert.title}"
                last = rule["last_triggered"].get(key)
                now = datetime.now()
                
                if last and (now - last) < rule["duration"]:
                    return True
                
                rule["last_triggered"][key] = now
        
        return False
    
    async def send_alert(self, alert: Alert) -> bool:
        """发送告警"""
        self.alerts[alert.id] = alert
        success = True
        
        for channel in alert.channels:
            if channel in self.notifiers:
                try:
                    result = await self.notifiers[channel].send(alert)
                    if not result:
                        success = False
                except Exception as e:
                    logger.error(f"告警发送失败 {channel}: {e}")
                    success = False
        
        if success:
            alert.sent_at = datetime.now()
        
        return success
    
    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """确认告警"""
        if alert_id in self.alerts:
            self.alerts[alert_id].acknowledged_at = datetime.now()
            logger.info(f"告警 {alert_id} 已被 {user} 确认")
            return True
        return False


# ==================== SOAR自动响应 ====================

@dataclass
class PlaybookStep:
    """剧本步骤"""
    id: str
    name: str
    action: str
    parameters: Dict[str, Any]
    condition: Optional[str] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    timeout: int = 300


@dataclass
class Playbook:
    """响应剧本"""
    id: str
    name: str
    description: str
    trigger_conditions: List[Dict]
    steps: List[PlaybookStep]
    enabled: bool = True
    version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_conditions": self.trigger_conditions,
            "steps": [{"id": s.id, "name": s.name, "action": s.action, 
                      "parameters": s.parameters} for s in self.steps],
            "enabled": self.enabled,
            "version": self.version
        }


@dataclass
class PlaybookExecution:
    """剧本执行记录"""
    id: str
    playbook_id: str
    incident_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    current_step: Optional[str]
    results: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


class SOAREngine:
    """安全编排自动化响应引擎"""
    
    def __init__(self):
        self.playbooks: Dict[str, Playbook] = {}
        self.executions: Dict[str, PlaybookExecution] = {}
        self.actions: Dict[str, Callable] = {}
        self._register_default_actions()
    
    def _register_default_actions(self):
        """注册默认动作"""
        self.actions.update({
            "block_ip": self._action_block_ip,
            "isolate_host": self._action_isolate_host,
            "disable_user": self._action_disable_user,
            "collect_evidence": self._action_collect_evidence,
            "send_notification": self._action_send_notification,
            "create_ticket": self._action_create_ticket,
            "run_scan": self._action_run_scan,
            "backup_data": self._action_backup_data,
            "restore_config": self._action_restore_config,
            "update_firewall": self._action_update_firewall,
        })
    
    def register_playbook(self, playbook: Playbook):
        """注册剧本"""
        self.playbooks[playbook.id] = playbook
        logger.info(f"注册剧本: {playbook.name}")
    
    def register_action(self, name: str, action: Callable):
        """注册动作"""
        self.actions[name] = action
    
    async def trigger(self, incident: Incident) -> Optional[PlaybookExecution]:
        """触发剧本"""
        for playbook in self.playbooks.values():
            if not playbook.enabled:
                continue
            
            if self._match_conditions(incident, playbook.trigger_conditions):
                return await self.execute_playbook(playbook.id, incident)
        
        return None
    
    def _match_conditions(
        self,
        incident: Incident,
        conditions: List[Dict]
    ) -> bool:
        """匹配触发条件"""
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")
            
            incident_value = getattr(incident, field, None)
            if incident_value is None:
                incident_value = incident.metadata.get(field)
            
            if isinstance(incident_value, Enum):
                incident_value = incident_value.value
            
            if operator == "equals" and incident_value != value:
                return False
            elif operator == "in" and incident_value not in value:
                return False
            elif operator == "contains" and value not in str(incident_value):
                return False
            elif operator == "gt" and not (incident_value > value):
                return False
            elif operator == "lt" and not (incident_value < value):
                return False
        
        return True
    
    async def execute_playbook(
        self,
        playbook_id: str,
        incident: Incident
    ) -> PlaybookExecution:
        """执行剧本"""
        playbook = self.playbooks.get(playbook_id)
        if not playbook:
            raise ValueError(f"剧本不存在: {playbook_id}")
        
        execution = PlaybookExecution(
            id=str(uuid.uuid4())[:12],
            playbook_id=playbook_id,
            incident_id=incident.id,
            started_at=datetime.now(),
            completed_at=None,
            status="running",
            current_step=None
        )
        
        self.executions[execution.id] = execution
        incident.playbook_id = playbook_id
        
        try:
            for step in playbook.steps:
                execution.current_step = step.id
                execution.logs.append(f"[{datetime.now().isoformat()}] 执行步骤: {step.name}")
                
                # 检查条件
                if step.condition and not self._evaluate_condition(step.condition, execution.results):
                    execution.logs.append(f"  跳过 - 条件不满足")
                    continue
                
                # 执行动作
                action = self.actions.get(step.action)
                if action:
                    try:
                        result = await action(incident, step.parameters)
                        execution.results[step.id] = {"status": "success", "result": result}
                        execution.logs.append(f"  成功")
                        
                        incident.add_event(
                            "SOAR",
                            step.action,
                            f"自动执行: {step.name}"
                        )
                    except Exception as e:
                        execution.results[step.id] = {"status": "failed", "error": str(e)}
                        execution.logs.append(f"  失败: {e}")
                        
                        if step.on_failure:
                            # 执行失败处理
                            pass
                else:
                    execution.logs.append(f"  动作未注册: {step.action}")
            
            execution.status = "completed"
        except Exception as e:
            execution.status = "failed"
            execution.logs.append(f"执行失败: {e}")
        finally:
            execution.completed_at = datetime.now()
        
        return execution
    
    def _evaluate_condition(self, condition: str, results: Dict) -> bool:
        """评估条件"""
        try:
            return eval(condition, {"results": results})
        except Exception:
            return True
    
    # ========== 默认动作实现 ==========
    
    async def _action_block_ip(self, incident: Incident, params: Dict) -> Dict:
        """封禁IP"""
        ip = params.get("ip") or incident.indicators[0] if incident.indicators else None
        if not ip:
            raise ValueError("未指定IP")
        
        # 实际实现中调用防火墙API
        logger.info(f"封禁IP: {ip}")
        return {"blocked_ip": ip, "timestamp": datetime.now().isoformat()}
    
    async def _action_isolate_host(self, incident: Incident, params: Dict) -> Dict:
        """隔离主机"""
        host = params.get("host") or incident.affected_assets[0] if incident.affected_assets else None
        if not host:
            raise ValueError("未指定主机")
        
        logger.info(f"隔离主机: {host}")
        return {"isolated_host": host, "timestamp": datetime.now().isoformat()}
    
    async def _action_disable_user(self, incident: Incident, params: Dict) -> Dict:
        """禁用用户"""
        user = params.get("user")
        if not user:
            raise ValueError("未指定用户")
        
        logger.info(f"禁用用户: {user}")
        return {"disabled_user": user, "timestamp": datetime.now().isoformat()}
    
    async def _action_collect_evidence(self, incident: Incident, params: Dict) -> Dict:
        """收集证据"""
        evidence_types = params.get("types", ["logs", "network", "memory"])
        
        collected = []
        for etype in evidence_types:
            collected.append({
                "type": etype,
                "path": f"/evidence/{incident.id}/{etype}",
                "collected_at": datetime.now().isoformat()
            })
        
        return {"evidence": collected}
    
    async def _action_send_notification(self, incident: Incident, params: Dict) -> Dict:
        """发送通知"""
        channels = params.get("channels", ["email"])
        recipients = params.get("recipients", [])
        
        logger.info(f"发送通知: {channels} -> {recipients}")
        return {"notified": True, "channels": channels, "recipients": recipients}
    
    async def _action_create_ticket(self, incident: Incident, params: Dict) -> Dict:
        """创建工单"""
        system = params.get("system", "internal")
        priority = params.get("priority", "high")
        
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"创建工单: {ticket_id}")
        return {"ticket_id": ticket_id, "system": system, "priority": priority}
    
    async def _action_run_scan(self, incident: Incident, params: Dict) -> Dict:
        """运行扫描"""
        scan_type = params.get("type", "quick")
        target = params.get("target", incident.affected_assets[0] if incident.affected_assets else "all")
        
        logger.info(f"运行扫描: {scan_type} on {target}")
        return {"scan_type": scan_type, "target": target, "status": "initiated"}
    
    async def _action_backup_data(self, incident: Incident, params: Dict) -> Dict:
        """备份数据"""
        targets = params.get("targets", [])
        
        logger.info(f"备份数据: {targets}")
        return {"backed_up": targets, "timestamp": datetime.now().isoformat()}
    
    async def _action_restore_config(self, incident: Incident, params: Dict) -> Dict:
        """恢复配置"""
        config_name = params.get("config")
        version = params.get("version", "latest")
        
        logger.info(f"恢复配置: {config_name} v{version}")
        return {"restored": config_name, "version": version}
    
    async def _action_update_firewall(self, incident: Incident, params: Dict) -> Dict:
        """更新防火墙"""
        rules = params.get("rules", [])
        
        logger.info(f"更新防火墙规则: {len(rules)} rules")
        return {"rules_updated": len(rules), "timestamp": datetime.now().isoformat()}


# ==================== 事件响应管理器 ====================

class IncidentResponseManager:
    """事件响应管理器"""
    
    def __init__(self):
        self.incidents: Dict[str, Incident] = {}
        self.alert_manager = AlertManager()
        self.soar_engine = SOAREngine()
        self._setup_default_playbooks()
    
    def _setup_default_playbooks(self):
        """设置默认剧本"""
        # 暴力破解响应剧本
        brute_force_playbook = Playbook(
            id="pb_brute_force",
            name="暴力破解响应",
            description="检测到暴力破解时自动响应",
            trigger_conditions=[
                {"field": "category", "operator": "equals", "value": "intrusion"},
                {"field": "severity", "operator": "in", "value": ["P1", "P2"]}
            ],
            steps=[
                PlaybookStep(
                    id="step1",
                    name="封禁攻击IP",
                    action="block_ip",
                    parameters={}
                ),
                PlaybookStep(
                    id="step2",
                    name="收集证据",
                    action="collect_evidence",
                    parameters={"types": ["logs", "network"]}
                ),
                PlaybookStep(
                    id="step3",
                    name="发送告警",
                    action="send_notification",
                    parameters={"channels": ["email", "slack"]}
                ),
                PlaybookStep(
                    id="step4",
                    name="创建工单",
                    action="create_ticket",
                    parameters={"priority": "high"}
                )
            ]
        )
        
        # 数据泄露响应剧本
        data_breach_playbook = Playbook(
            id="pb_data_breach",
            name="数据泄露响应",
            description="检测到数据泄露时自动响应",
            trigger_conditions=[
                {"field": "category", "operator": "equals", "value": "data_breach"}
            ],
            steps=[
                PlaybookStep(
                    id="step1",
                    name="隔离受影响系统",
                    action="isolate_host",
                    parameters={}
                ),
                PlaybookStep(
                    id="step2",
                    name="备份当前数据",
                    action="backup_data",
                    parameters={}
                ),
                PlaybookStep(
                    id="step3",
                    name="收集取证",
                    action="collect_evidence",
                    parameters={"types": ["logs", "network", "memory", "disk"]}
                ),
                PlaybookStep(
                    id="step4",
                    name="紧急通知",
                    action="send_notification",
                    parameters={"channels": ["email", "sms", "slack"], "recipients": ["security-team", "management"]}
                )
            ]
        )
        
        # 恶意软件响应剧本
        malware_playbook = Playbook(
            id="pb_malware",
            name="恶意软件响应",
            description="检测到恶意软件时自动响应",
            trigger_conditions=[
                {"field": "category", "operator": "equals", "value": "malware"}
            ],
            steps=[
                PlaybookStep(
                    id="step1",
                    name="隔离感染主机",
                    action="isolate_host",
                    parameters={}
                ),
                PlaybookStep(
                    id="step2",
                    name="运行全面扫描",
                    action="run_scan",
                    parameters={"type": "full"}
                ),
                PlaybookStep(
                    id="step3",
                    name="收集样本",
                    action="collect_evidence",
                    parameters={"types": ["malware_sample", "memory", "logs"]}
                )
            ]
        )
        
        self.soar_engine.register_playbook(brute_force_playbook)
        self.soar_engine.register_playbook(data_breach_playbook)
        self.soar_engine.register_playbook(malware_playbook)
    
    async def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        category: IncidentCategory,
        source: str,
        **kwargs
    ) -> Incident:
        """创建安全事件"""
        incident = Incident(
            id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            title=title,
            description=description,
            severity=severity,
            status=IncidentStatus.NEW,
            category=category,
            source=source,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            tags=kwargs.get("tags", []),
            affected_assets=kwargs.get("affected_assets", []),
            indicators=kwargs.get("indicators", []),
            metadata=kwargs.get("metadata", {})
        )
        
        incident.add_event("System", "created", "事件已创建")
        
        self.incidents[incident.id] = incident
        
        # 创建告警
        alert = Alert(
            id=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            title=f"新安全事件: {title}",
            message=description,
            severity=severity,
            source=source,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            created_at=datetime.now(),
            incident_id=incident.id
        )
        await self.alert_manager.send_alert(alert)
        
        # 触发SOAR
        await self.soar_engine.trigger(incident)
        
        return incident
    
    async def update_incident(
        self,
        incident_id: str,
        user: str,
        **updates
    ) -> Optional[Incident]:
        """更新事件"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        
        for key, value in updates.items():
            if hasattr(incident, key):
                setattr(incident, key, value)
        
        incident.updated_at = datetime.now()
        incident.add_event(user, "updated", f"更新字段: {', '.join(updates.keys())}")
        
        return incident
    
    async def assign_incident(
        self,
        incident_id: str,
        assignee: str,
        assigner: str
    ) -> Optional[Incident]:
        """分配事件"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        
        incident.assigned_to = assignee
        incident.status = IncidentStatus.ACKNOWLEDGED
        incident.updated_at = datetime.now()
        incident.add_event(assigner, "assigned", f"分配给 {assignee}")
        
        return incident
    
    async def resolve_incident(
        self,
        incident_id: str,
        resolver: str,
        resolution: str
    ) -> Optional[Incident]:
        """解决事件"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now()
        incident.updated_at = datetime.now()
        incident.add_event(resolver, "resolved", resolution)
        
        return incident
    
    async def close_incident(
        self,
        incident_id: str,
        closer: str,
        summary: str
    ) -> Optional[Incident]:
        """关闭事件"""
        incident = self.incidents.get(incident_id)
        if not incident:
            return None
        
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = datetime.now()
        incident.updated_at = datetime.now()
        incident.add_event(closer, "closed", summary)
        
        return incident
    
    def get_active_incidents(self) -> List[Incident]:
        """获取活跃事件"""
        active_statuses = [
            IncidentStatus.NEW,
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.CONTAINMENT,
            IncidentStatus.ERADICATION,
            IncidentStatus.RECOVERY
        ]
        return [i for i in self.incidents.values() if i.status in active_statuses]
    
    def get_incident_metrics(self) -> Dict[str, Any]:
        """获取事件指标"""
        total = len(self.incidents)
        if total == 0:
            return {"total": 0}
        
        by_severity = defaultdict(int)
        by_status = defaultdict(int)
        by_category = defaultdict(int)
        
        mttr_list = []  # Mean Time To Resolve
        
        for incident in self.incidents.values():
            by_severity[incident.severity.value] += 1
            by_status[incident.status.value] += 1
            by_category[incident.category.value] += 1
            
            if incident.resolved_at:
                mttr = (incident.resolved_at - incident.created_at).total_seconds() / 3600
                mttr_list.append(mttr)
        
        return {
            "total": total,
            "active": len(self.get_active_incidents()),
            "by_severity": dict(by_severity),
            "by_status": dict(by_status),
            "by_category": dict(by_category),
            "mttr_hours": sum(mttr_list) / len(mttr_list) if mttr_list else 0
        }


# ==================== 导出 ====================

__all__ = [
    # 枚举类型
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentCategory",
    "AlertChannel",
    # 数据模型
    "IncidentEvent",
    "Incident",
    "Alert",
    "PlaybookStep",
    "Playbook",
    "PlaybookExecution",
    # 通知器
    "AlertNotifier",
    "EmailNotifier",
    "WebhookNotifier",
    "DingTalkNotifier",
    "SlackNotifier",
    # 管理器
    "AlertManager",
    "SOAREngine",
    "IncidentResponseManager",
]
