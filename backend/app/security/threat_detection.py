# 地方志数据智能管理系统 - 威胁检测
"""入侵检测系统(IDS)、异常行为分析、威胁情报"""

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import structlog

logger = structlog.get_logger()


class ThreatCategory(str, Enum):
    """威胁类别"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    BOT_ATTACK = "bot_attack"
    DDOS = "ddos"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    MALWARE = "malware"
    ANOMALY = "anomaly"
    UNKNOWN = "unknown"


class ThreatSeverity(str, Enum):
    """威胁严重程度"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatAction(str, Enum):
    """响应动作"""
    LOG = "log"
    ALERT = "alert"
    BLOCK = "block"
    QUARANTINE = "quarantine"
    CHALLENGE = "challenge"  # CAPTCHA验证


@dataclass
class ThreatIndicator:
    """威胁指标(IoC)"""
    id: str
    indicator_type: str  # ip/domain/hash/pattern
    value: str
    threat_category: ThreatCategory
    severity: ThreatSeverity
    source: str  # 情报来源
    confidence: float  # 0-1
    first_seen: datetime = None
    last_seen: datetime = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        now = datetime.now()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now


@dataclass
class ThreatEvent:
    """威胁事件"""
    id: str
    timestamp: datetime
    category: ThreatCategory
    severity: ThreatSeverity
    source_ip: str
    target: str
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    matched_indicators: List[str] = field(default_factory=list)
    action_taken: ThreatAction = ThreatAction.LOG
    is_false_positive: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value,
            "severity": self.severity.value,
            "source_ip": self.source_ip,
            "target": self.target,
            "description": self.description,
            "evidence": self.evidence,
            "matched_indicators": self.matched_indicators,
            "action_taken": self.action_taken.value,
            "is_false_positive": self.is_false_positive
        }


class PatternDetector:
    """攻击模式检测器"""
    
    # SQL注入模式
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b.*\b(FROM|INTO|SET|TABLE|WHERE)\b)",
        r"('\s*(OR|AND)\s*'?\d*\s*=\s*'?\d*)",
        r"(--\s*$|#\s*$|/\*.*\*/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(;\s*(DROP|DELETE|UPDATE|INSERT)\s)",
        r"(SLEEP\s*\(\s*\d+\s*\))",
        r"(BENCHMARK\s*\()",
    ]
    
    # XSS模式
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript\s*:",
        r"on(click|load|error|mouseover|focus|blur)\s*=",
        r"<iframe[^>]*>",
        r"<img[^>]+onerror\s*=",
        r"expression\s*\(",
        r"eval\s*\(",
    ]
    
    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e/",
        r"\.\.%2f",
        r"/etc/passwd",
        r"/etc/shadow",
        r"c:\\windows",
    ]
    
    # 命令注入模式
    COMMAND_INJECTION_PATTERNS = [
        r";\s*(ls|cat|rm|wget|curl|nc|bash|sh)\b",
        r"\|\s*(ls|cat|rm|wget|curl|nc|bash|sh)\b",
        r"`[^`]+`",
        r"\$\([^)]+\)",
        r"&&\s*(ls|cat|rm|wget|curl)\b",
    ]
    
    def __init__(self):
        self._compiled_patterns: Dict[ThreatCategory, List[re.Pattern]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则模式"""
        self._compiled_patterns[ThreatCategory.SQL_INJECTION] = [
            re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS
        ]
        self._compiled_patterns[ThreatCategory.XSS] = [
            re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS
        ]
        self._compiled_patterns[ThreatCategory.PATH_TRAVERSAL] = [
            re.compile(p, re.IGNORECASE) for p in self.PATH_TRAVERSAL_PATTERNS
        ]
        self._compiled_patterns[ThreatCategory.COMMAND_INJECTION] = [
            re.compile(p, re.IGNORECASE) for p in self.COMMAND_INJECTION_PATTERNS
        ]
    
    def detect(self, text: str) -> List[Tuple[ThreatCategory, str, float]]:
        """检测攻击模式，返回(类别, 匹配内容, 置信度)"""
        if not text:
            return []
        
        results = []
        
        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    match_str = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    results.append((category, match_str[:100], 0.9))
        
        return results


class AnomalyDetector:
    """异常行为检测器"""
    
    def __init__(self):
        # 行为基线
        self._request_counts: Dict[str, List[Tuple[datetime, int]]] = defaultdict(list)
        self._endpoint_stats: Dict[str, Dict[str, float]] = {}
        self._user_patterns: Dict[int, Dict[str, Any]] = {}
        
        # 阈值
        self.request_rate_threshold = 100  # 每分钟
        self.error_rate_threshold = 0.3    # 30%
        self.data_volume_threshold = 10 * 1024 * 1024  # 10MB
    
    def record_request(
        self,
        ip: str,
        user_id: Optional[int],
        endpoint: str,
        response_code: int,
        response_size: int
    ):
        """记录请求用于基线计算"""
        now = datetime.now()
        
        # IP请求计数
        key = f"ip:{ip}"
        self._request_counts[key].append((now, 1))
        
        # 用户请求计数
        if user_id:
            user_key = f"user:{user_id}"
            self._request_counts[user_key].append((now, 1))
        
        # 端点统计
        if endpoint not in self._endpoint_stats:
            self._endpoint_stats[endpoint] = {
                "total": 0,
                "errors": 0,
                "total_size": 0
            }
        
        self._endpoint_stats[endpoint]["total"] += 1
        if response_code >= 400:
            self._endpoint_stats[endpoint]["errors"] += 1
        self._endpoint_stats[endpoint]["total_size"] += response_size
    
    def detect_anomalies(
        self,
        ip: str,
        user_id: Optional[int],
        endpoint: str,
        request_data: Dict[str, Any]
    ) -> List[Tuple[ThreatCategory, str, float]]:
        """检测异常行为"""
        anomalies = []
        now = datetime.now()
        
        # 1. 请求频率异常
        rate = self._calculate_request_rate(f"ip:{ip}", now)
        if rate > self.request_rate_threshold:
            anomalies.append((
                ThreatCategory.DDOS,
                f"请求频率异常: {rate}/分钟",
                min(rate / (self.request_rate_threshold * 2), 1.0)
            ))
        
        # 2. 数据量异常（可能的数据泄露）
        data_size = len(str(request_data))
        if data_size > self.data_volume_threshold:
            anomalies.append((
                ThreatCategory.DATA_EXFILTRATION,
                f"异常数据量: {data_size} bytes",
                0.7
            ))
        
        # 3. 用户行为异常
        if user_id:
            user_anomaly = self._detect_user_anomaly(user_id, endpoint, now)
            if user_anomaly:
                anomalies.append(user_anomaly)
        
        return anomalies
    
    def _calculate_request_rate(self, key: str, now: datetime) -> int:
        """计算请求频率（每分钟）"""
        cutoff = now - timedelta(minutes=1)
        
        # 清理旧记录
        self._request_counts[key] = [
            (t, c) for t, c in self._request_counts[key] if t > cutoff
        ]
        
        return sum(c for _, c in self._request_counts[key])
    
    def _detect_user_anomaly(
        self,
        user_id: int,
        endpoint: str,
        now: datetime
    ) -> Optional[Tuple[ThreatCategory, str, float]]:
        """检测用户行为异常"""
        key = f"user:{user_id}"
        
        # 检查不寻常的访问模式
        if key not in self._user_patterns:
            self._user_patterns[key] = {
                "endpoints": set(),
                "active_hours": set(),
                "first_seen": now
            }
        
        pattern = self._user_patterns[key]
        pattern["endpoints"].add(endpoint)
        pattern["active_hours"].add(now.hour)
        
        # 新用户访问敏感端点
        if (now - pattern["first_seen"]).days < 1:
            sensitive_endpoints = ['/admin', '/api/users', '/api/export', '/api/config']
            if any(e in endpoint for e in sensitive_endpoints):
                return (
                    ThreatCategory.PRIVILEGE_ESCALATION,
                    f"新用户访问敏感端点: {endpoint}",
                    0.6
                )
        
        return None


class ThreatIntelligence:
    """威胁情报管理"""
    
    def __init__(self):
        self.indicators: Dict[str, ThreatIndicator] = {}
        self._ip_set: Set[str] = set()
        self._domain_set: Set[str] = set()
        self._hash_set: Set[str] = set()
    
    def add_indicator(self, indicator: ThreatIndicator):
        """添加威胁指标"""
        self.indicators[indicator.id] = indicator
        
        if indicator.indicator_type == "ip":
            self._ip_set.add(indicator.value)
        elif indicator.indicator_type == "domain":
            self._domain_set.add(indicator.value)
        elif indicator.indicator_type == "hash":
            self._hash_set.add(indicator.value)
    
    def check_ip(self, ip: str) -> Optional[ThreatIndicator]:
        """检查IP是否在威胁情报中"""
        if ip in self._ip_set:
            for indicator in self.indicators.values():
                if indicator.indicator_type == "ip" and indicator.value == ip:
                    indicator.last_seen = datetime.now()
                    return indicator
        return None
    
    def check_domain(self, domain: str) -> Optional[ThreatIndicator]:
        """检查域名是否在威胁情报中"""
        if domain in self._domain_set:
            for indicator in self.indicators.values():
                if indicator.indicator_type == "domain" and indicator.value == domain:
                    indicator.last_seen = datetime.now()
                    return indicator
        return None
    
    def load_threat_feed(self, feed_data: List[Dict]) -> int:
        """加载威胁情报源"""
        count = 0
        for item in feed_data:
            try:
                indicator = ThreatIndicator(
                    id=item.get("id", hashlib.md5(item["value"].encode()).hexdigest()[:16]),
                    indicator_type=item["type"],
                    value=item["value"],
                    threat_category=ThreatCategory(item.get("category", "unknown")),
                    severity=ThreatSeverity(item.get("severity", "medium")),
                    source=item.get("source", "unknown"),
                    confidence=item.get("confidence", 0.5),
                    tags=item.get("tags", [])
                )
                self.add_indicator(indicator)
                count += 1
            except Exception as e:
                logger.warning("加载威胁指标失败", error=str(e))
        
        logger.info("威胁情报加载完成", count=count)
        return count


class IntrusionDetectionSystem:
    """入侵检测系统(IDS)"""
    
    def __init__(
        self,
        on_threat: Optional[Callable[[ThreatEvent], None]] = None
    ):
        self.pattern_detector = PatternDetector()
        self.anomaly_detector = AnomalyDetector()
        self.threat_intel = ThreatIntelligence()
        self.on_threat = on_threat
        
        # 事件存储
        self.events: List[ThreatEvent] = []
        self._event_counts: Dict[str, int] = defaultdict(int)
        
        # 阻止列表
        self._blocked_ips: Dict[str, datetime] = {}
        self._block_duration = timedelta(hours=1)
    
    async def analyze_request(
        self,
        ip: str,
        user_id: Optional[int],
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[str],
        query_params: Dict[str, str]
    ) -> Tuple[bool, List[ThreatEvent]]:
        """
        分析请求，返回(是否允许, 检测到的威胁)
        """
        events = []
        
        # 1. 检查IP是否被阻止
        if self.is_blocked(ip):
            return False, []
        
        # 2. 检查威胁情报
        intel_match = self.threat_intel.check_ip(ip)
        if intel_match:
            event = self._create_event(
                ThreatCategory(intel_match.threat_category.value),
                intel_match.severity,
                ip,
                path,
                f"IP匹配威胁情报: {intel_match.source}",
                {"indicator_id": intel_match.id}
            )
            events.append(event)
            
            if intel_match.severity in [ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]:
                self.block_ip(ip)
                return False, events
        
        # 3. 模式检测
        content_to_check = f"{path} {body or ''} {' '.join(query_params.values())}"
        pattern_matches = self.pattern_detector.detect(content_to_check)
        
        for category, match, confidence in pattern_matches:
            severity = self._determine_severity(category, confidence)
            event = self._create_event(
                category,
                severity,
                ip,
                path,
                f"检测到攻击模式: {match[:50]}",
                {"pattern": match, "confidence": confidence}
            )
            events.append(event)
            
            if severity in [ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]:
                self.block_ip(ip)
                return False, events
        
        # 4. 异常检测
        anomalies = self.anomaly_detector.detect_anomalies(
            ip, user_id, path, {"body": body, "params": query_params}
        )
        
        for category, description, confidence in anomalies:
            event = self._create_event(
                category,
                ThreatSeverity.MEDIUM,
                ip,
                path,
                description,
                {"confidence": confidence}
            )
            events.append(event)
        
        # 5. 记录和通知
        for event in events:
            self.events.append(event)
            self._event_counts[event.category.value] += 1
            
            if self.on_threat:
                try:
                    self.on_threat(event)
                except Exception as e:
                    logger.error("威胁回调失败", error=str(e))
        
        # 允许请求（即使检测到低级威胁也可能允许）
        return True, events
    
    def _create_event(
        self,
        category: ThreatCategory,
        severity: ThreatSeverity,
        ip: str,
        target: str,
        description: str,
        evidence: Dict
    ) -> ThreatEvent:
        """创建威胁事件"""
        return ThreatEvent(
            id=f"threat_{int(time.time()*1000)}_{hashlib.md5(ip.encode()).hexdigest()[:8]}",
            timestamp=datetime.now(),
            category=category,
            severity=severity,
            source_ip=ip,
            target=target,
            description=description,
            evidence=evidence,
            action_taken=ThreatAction.LOG if severity == ThreatSeverity.LOW else ThreatAction.ALERT
        )
    
    def _determine_severity(
        self,
        category: ThreatCategory,
        confidence: float
    ) -> ThreatSeverity:
        """确定威胁严重程度"""
        high_severity_categories = [
            ThreatCategory.SQL_INJECTION,
            ThreatCategory.COMMAND_INJECTION,
            ThreatCategory.DATA_EXFILTRATION
        ]
        
        if category in high_severity_categories:
            if confidence >= 0.8:
                return ThreatSeverity.CRITICAL
            return ThreatSeverity.HIGH
        
        if confidence >= 0.9:
            return ThreatSeverity.HIGH
        if confidence >= 0.7:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW
    
    def block_ip(self, ip: str, duration: timedelta = None):
        """阻止IP"""
        self._blocked_ips[ip] = datetime.now()
        logger.warning("IP已被阻止", ip=ip)
    
    def unblock_ip(self, ip: str):
        """解除IP阻止"""
        self._blocked_ips.pop(ip, None)
    
    def is_blocked(self, ip: str) -> bool:
        """检查IP是否被阻止"""
        if ip not in self._blocked_ips:
            return False
        
        blocked_time = self._blocked_ips[ip]
        if datetime.now() - blocked_time > self._block_duration:
            self.unblock_ip(ip)
            return False
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        
        recent_events = [e for e in self.events if e.timestamp > last_24h]
        
        by_category = defaultdict(int)
        by_severity = defaultdict(int)
        by_ip = defaultdict(int)
        
        for event in recent_events:
            by_category[event.category.value] += 1
            by_severity[event.severity.value] += 1
            by_ip[event.source_ip] += 1
        
        # Top攻击来源IP
        top_ips = sorted(by_ip.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_events_24h": len(recent_events),
            "by_category": dict(by_category),
            "by_severity": dict(by_severity),
            "top_attacking_ips": top_ips,
            "blocked_ips": len(self._blocked_ips),
            "threat_indicators": len(self.threat_intel.indicators)
        }


# FastAPI中间件
class ThreatDetectionMiddleware:
    """威胁检测中间件"""
    
    def __init__(self, app, ids: IntrusionDetectionSystem):
        self.app = app
        self.ids = ids
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        from starlette.requests import Request
        request = Request(scope, receive)
        
        ip = request.client.host if request.client else "unknown"
        
        # 分析请求
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = (await request.body()).decode()
            except:
                pass
        
        allowed, events = await self.ids.analyze_request(
            ip=ip,
            user_id=scope.get("state", {}).get("user_id"),
            method=request.method,
            path=str(request.url.path),
            headers=dict(request.headers),
            body=body,
            query_params=dict(request.query_params)
        )
        
        if not allowed:
            # 返回403
            response_body = b'{"error": "Access Denied"}'
            await send({
                "type": "http.response.start",
                "status": 403,
                "headers": [[b"content-type", b"application/json"]]
            })
            await send({
                "type": "http.response.body",
                "body": response_body
            })
            return
        
        return await self.app(scope, receive, send)
