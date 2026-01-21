# 地方志数据智能管理系统 - 网络安全
"""WAF规则、DDoS防护、IP过滤、流量分析"""

import asyncio
import hashlib
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import structlog

logger = structlog.get_logger()


class WAFAction(str, Enum):
    """WAF动作"""
    ALLOW = "allow"
    BLOCK = "block"
    CHALLENGE = "challenge"  # CAPTCHA
    LOG = "log"
    RATE_LIMIT = "rate_limit"


class RuleCategory(str, Enum):
    """规则类别"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    PATH_TRAVERSAL = "path_traversal"
    RCE = "rce"  # 远程代码执行
    FILE_INCLUSION = "file_inclusion"
    PROTOCOL = "protocol"
    BOT = "bot"
    CUSTOM = "custom"


@dataclass
class WAFRule:
    """WAF规则"""
    id: str
    name: str
    category: RuleCategory
    pattern: str
    target: str  # body/url/header/cookie
    action: WAFAction
    severity: int  # 1-10
    enabled: bool = True
    compiled_pattern: re.Pattern = None
    
    def __post_init__(self):
        if self.compiled_pattern is None:
            self.compiled_pattern = re.compile(self.pattern, re.IGNORECASE)
    
    def match(self, content: str) -> bool:
        """匹配内容"""
        if not content:
            return False
        return bool(self.compiled_pattern.search(content))


@dataclass
class IPReputation:
    """IP信誉"""
    ip: str
    score: float  # 0-100, 100为可信
    category: str  # clean/suspicious/malicious/tor/proxy/vpn
    country: str = ""
    asn: str = ""
    last_seen: datetime = None
    threat_types: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.last_seen:
            self.last_seen = datetime.now()


class WAFEngine:
    """WAF引擎"""
    
    # 内置规则
    BUILTIN_RULES = [
        # SQL注入规则
        WAFRule(
            id="sqli_001",
            name="SQL注入 - UNION攻击",
            category=RuleCategory.SQL_INJECTION,
            pattern=r"(?:union\s+(?:all\s+)?select)",
            target="body",
            action=WAFAction.BLOCK,
            severity=9
        ),
        WAFRule(
            id="sqli_002",
            name="SQL注入 - OR条件",
            category=RuleCategory.SQL_INJECTION,
            pattern=r"(?:'\s*(?:or|and)\s*'?\d*\s*[=<>])",
            target="body",
            action=WAFAction.BLOCK,
            severity=8
        ),
        WAFRule(
            id="sqli_003",
            name="SQL注入 - 注释",
            category=RuleCategory.SQL_INJECTION,
            pattern=r"(?:--\s*$|/\*.*?\*/|#\s*$)",
            target="body",
            action=WAFAction.LOG,
            severity=5
        ),
        
        # XSS规则
        WAFRule(
            id="xss_001",
            name="XSS - Script标签",
            category=RuleCategory.XSS,
            pattern=r"<script[^>]*>.*?</script>",
            target="body",
            action=WAFAction.BLOCK,
            severity=9
        ),
        WAFRule(
            id="xss_002",
            name="XSS - 事件处理器",
            category=RuleCategory.XSS,
            pattern=r"on(?:click|load|error|mouseover|focus)\s*=",
            target="body",
            action=WAFAction.BLOCK,
            severity=8
        ),
        WAFRule(
            id="xss_003",
            name="XSS - JavaScript协议",
            category=RuleCategory.XSS,
            pattern=r"javascript\s*:",
            target="body",
            action=WAFAction.BLOCK,
            severity=8
        ),
        
        # 路径遍历规则
        WAFRule(
            id="pt_001",
            name="路径遍历 - 双点",
            category=RuleCategory.PATH_TRAVERSAL,
            pattern=r"(?:\.\./|\.\.\\)",
            target="url",
            action=WAFAction.BLOCK,
            severity=7
        ),
        WAFRule(
            id="pt_002",
            name="路径遍历 - 敏感文件",
            category=RuleCategory.PATH_TRAVERSAL,
            pattern=r"(?:/etc/passwd|/etc/shadow|/windows/system32)",
            target="url",
            action=WAFAction.BLOCK,
            severity=9
        ),
        
        # 远程代码执行规则
        WAFRule(
            id="rce_001",
            name="RCE - 命令注入",
            category=RuleCategory.RCE,
            pattern=r"(?:;\s*(?:ls|cat|rm|wget|curl|nc|bash|sh)\b)",
            target="body",
            action=WAFAction.BLOCK,
            severity=10
        ),
        
        # 协议攻击
        WAFRule(
            id="proto_001",
            name="HTTP请求走私",
            category=RuleCategory.PROTOCOL,
            pattern=r"(?:transfer-encoding\s*:\s*chunked.*content-length)",
            target="header",
            action=WAFAction.BLOCK,
            severity=9
        ),
        
        # Bot检测
        WAFRule(
            id="bot_001",
            name="恶意Bot User-Agent",
            category=RuleCategory.BOT,
            pattern=r"(?:sqlmap|nikto|nmap|masscan|zgrab|nuclei)",
            target="header",
            action=WAFAction.BLOCK,
            severity=7
        )
    ]
    
    def __init__(self):
        self.rules: Dict[str, WAFRule] = {}
        self.custom_rules: Dict[str, WAFRule] = {}
        
        # 加载内置规则
        for rule in self.BUILTIN_RULES:
            self.rules[rule.id] = rule
    
    def add_rule(self, rule: WAFRule):
        """添加规则"""
        self.custom_rules[rule.id] = rule
    
    def remove_rule(self, rule_id: str):
        """移除规则"""
        self.custom_rules.pop(rule_id, None)
    
    def enable_rule(self, rule_id: str):
        """启用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
        if rule_id in self.custom_rules:
            self.custom_rules[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str):
        """禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
        if rule_id in self.custom_rules:
            self.custom_rules[rule_id].enabled = False
    
    def inspect(
        self,
        url: str = "",
        body: str = "",
        headers: Dict[str, str] = None
    ) -> Tuple[WAFAction, List[WAFRule]]:
        """检查请求"""
        matched_rules = []
        headers = headers or {}
        
        all_rules = list(self.rules.values()) + list(self.custom_rules.values())
        
        for rule in all_rules:
            if not rule.enabled:
                continue
            
            content = ""
            if rule.target == "url":
                content = url
            elif rule.target == "body":
                content = body
            elif rule.target == "header":
                content = " ".join(f"{k}: {v}" for k, v in headers.items())
            elif rule.target == "cookie":
                content = headers.get("Cookie", "")
            
            if rule.match(content):
                matched_rules.append(rule)
        
        if not matched_rules:
            return WAFAction.ALLOW, []
        
        # 返回最严重规则的动作
        matched_rules.sort(key=lambda r: r.severity, reverse=True)
        return matched_rules[0].action, matched_rules


class DDoSProtection:
    """DDoS防护"""
    
    def __init__(
        self,
        requests_per_second: int = 100,
        requests_per_minute: int = 1000,
        burst_limit: int = 50,
        ban_duration_seconds: int = 300
    ):
        self.rps_limit = requests_per_second
        self.rpm_limit = requests_per_minute
        self.burst_limit = burst_limit
        self.ban_duration = ban_duration_seconds
        
        self._request_counts: Dict[str, List[float]] = defaultdict(list)
        self._banned_ips: Dict[str, float] = {}
        self._global_requests: List[float] = []
    
    def record_request(self, ip: str) -> bool:
        """
        记录请求，返回是否允许
        """
        now = time.time()
        
        # 检查是否被禁
        if self.is_banned(ip):
            return False
        
        # 清理过期记录
        self._cleanup(ip, now)
        
        # 添加请求记录
        self._request_counts[ip].append(now)
        self._global_requests.append(now)
        
        # 检查限制
        if self._check_limits(ip, now):
            self._ban_ip(ip, now)
            return False
        
        return True
    
    def _cleanup(self, ip: str, now: float):
        """清理过期记录"""
        minute_ago = now - 60
        
        self._request_counts[ip] = [
            t for t in self._request_counts[ip] if t > minute_ago
        ]
        
        self._global_requests = [
            t for t in self._global_requests if t > minute_ago
        ]
    
    def _check_limits(self, ip: str, now: float) -> bool:
        """检查是否超限"""
        requests = self._request_counts[ip]
        
        # 每秒限制
        second_ago = now - 1
        rps = sum(1 for t in requests if t > second_ago)
        if rps > self.rps_limit:
            logger.warning("超过RPS限制", ip=ip, rps=rps)
            return True
        
        # 每分钟限制
        if len(requests) > self.rpm_limit:
            logger.warning("超过RPM限制", ip=ip, rpm=len(requests))
            return True
        
        # 突发检测
        last_second = [t for t in requests if t > second_ago]
        if len(last_second) > self.burst_limit:
            logger.warning("检测到突发流量", ip=ip, burst=len(last_second))
            return True
        
        return False
    
    def _ban_ip(self, ip: str, now: float):
        """禁止IP"""
        self._banned_ips[ip] = now
        logger.warning("IP已被DDoS防护禁止", ip=ip)
    
    def is_banned(self, ip: str) -> bool:
        """检查IP是否被禁"""
        if ip not in self._banned_ips:
            return False
        
        ban_time = self._banned_ips[ip]
        if time.time() - ban_time > self.ban_duration:
            del self._banned_ips[ip]
            return False
        
        return True
    
    def unban_ip(self, ip: str):
        """解禁IP"""
        self._banned_ips.pop(ip, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        now = time.time()
        minute_ago = now - 60
        
        return {
            "global_rpm": len([t for t in self._global_requests if t > minute_ago]),
            "banned_ips": len(self._banned_ips),
            "tracked_ips": len(self._request_counts)
        }


class IPFilter:
    """IP过滤器"""
    
    def __init__(self):
        self.whitelist: Set[str] = set()
        self.blacklist: Set[str] = set()
        self.country_blacklist: Set[str] = set()
        self.asn_blacklist: Set[str] = set()
        
        # IP信誉库
        self.reputation_cache: Dict[str, IPReputation] = {}
    
    def add_to_whitelist(self, ip: str):
        """添加到白名单"""
        self.whitelist.add(ip)
        self.blacklist.discard(ip)
    
    def add_to_blacklist(self, ip: str, reason: str = ""):
        """添加到黑名单"""
        self.blacklist.add(ip)
        self.whitelist.discard(ip)
        logger.info("IP已加入黑名单", ip=ip, reason=reason)
    
    def remove_from_blacklist(self, ip: str):
        """从黑名单移除"""
        self.blacklist.discard(ip)
    
    def block_country(self, country_code: str):
        """屏蔽国家"""
        self.country_blacklist.add(country_code.upper())
    
    def block_asn(self, asn: str):
        """屏蔽ASN"""
        self.asn_blacklist.add(asn)
    
    def check_ip(self, ip: str) -> Tuple[bool, str]:
        """
        检查IP，返回(是否允许, 原因)
        """
        # 白名单优先
        if ip in self.whitelist:
            return True, "whitelist"
        
        # 黑名单
        if ip in self.blacklist:
            return False, "blacklist"
        
        # 检查IP信誉
        reputation = self.reputation_cache.get(ip)
        if reputation:
            # 国家屏蔽
            if reputation.country in self.country_blacklist:
                return False, f"blocked_country:{reputation.country}"
            
            # ASN屏蔽
            if reputation.asn in self.asn_blacklist:
                return False, f"blocked_asn:{reputation.asn}"
            
            # 信誉检查
            if reputation.score < 30:
                return False, f"low_reputation:{reputation.score}"
            
            if reputation.category == "malicious":
                return False, "malicious_ip"
        
        return True, "allowed"
    
    def update_reputation(self, reputation: IPReputation):
        """更新IP信誉"""
        self.reputation_cache[reputation.ip] = reputation
    
    def _ip_in_range(self, ip: str, cidr: str) -> bool:
        """检查IP是否在CIDR范围内"""
        try:
            import ipaddress
            return ipaddress.ip_address(ip) in ipaddress.ip_network(cidr, strict=False)
        except:
            return False


class TrafficAnalyzer:
    """流量分析器"""
    
    def __init__(self):
        self._request_history: List[Dict[str, Any]] = []
        self._anomaly_callbacks: List[Callable] = []
        self._baseline: Dict[str, float] = {}
    
    def record_request(
        self,
        ip: str,
        path: str,
        method: str,
        response_code: int,
        response_time_ms: float,
        request_size: int,
        response_size: int
    ):
        """记录请求"""
        self._request_history.append({
            "timestamp": time.time(),
            "ip": ip,
            "path": path,
            "method": method,
            "response_code": response_code,
            "response_time_ms": response_time_ms,
            "request_size": request_size,
            "response_size": response_size
        })
        
        # 限制历史大小
        if len(self._request_history) > 10000:
            self._request_history = self._request_history[-5000:]
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """检测异常"""
        anomalies = []
        now = time.time()
        recent = [r for r in self._request_history if now - r["timestamp"] < 300]
        
        if not recent:
            return []
        
        # 1. 异常高的请求量
        ip_counts = defaultdict(int)
        for req in recent:
            ip_counts[req["ip"]] += 1
        
        avg_count = sum(ip_counts.values()) / max(len(ip_counts), 1)
        for ip, count in ip_counts.items():
            if count > avg_count * 5:
                anomalies.append({
                    "type": "high_request_rate",
                    "ip": ip,
                    "count": count,
                    "avg": avg_count
                })
        
        # 2. 异常高的错误率
        error_counts = defaultdict(int)
        total_counts = defaultdict(int)
        for req in recent:
            total_counts[req["ip"]] += 1
            if req["response_code"] >= 400:
                error_counts[req["ip"]] += 1
        
        for ip, errors in error_counts.items():
            error_rate = errors / total_counts[ip]
            if error_rate > 0.5 and total_counts[ip] > 10:
                anomalies.append({
                    "type": "high_error_rate",
                    "ip": ip,
                    "error_rate": error_rate,
                    "total": total_counts[ip]
                })
        
        # 3. 扫描行为
        path_counts = defaultdict(lambda: defaultdict(int))
        for req in recent:
            path_counts[req["ip"]][req["path"]] += 1
        
        for ip, paths in path_counts.items():
            if len(paths) > 50:  # 短时间内访问大量不同路径
                anomalies.append({
                    "type": "scanning_behavior",
                    "ip": ip,
                    "unique_paths": len(paths)
                })
        
        return anomalies
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        now = time.time()
        last_minute = [r for r in self._request_history if now - r["timestamp"] < 60]
        last_hour = [r for r in self._request_history if now - r["timestamp"] < 3600]
        
        if not last_minute:
            return {"rpm": 0, "rph": 0}
        
        avg_response_time = sum(r["response_time_ms"] for r in last_minute) / len(last_minute)
        
        error_count = sum(1 for r in last_minute if r["response_code"] >= 400)
        error_rate = error_count / len(last_minute)
        
        return {
            "rpm": len(last_minute),
            "rph": len(last_hour),
            "avg_response_time_ms": round(avg_response_time, 2),
            "error_rate": round(error_rate, 4),
            "unique_ips_last_minute": len(set(r["ip"] for r in last_minute))
        }


class NetworkSecurityManager:
    """网络安全管理器"""
    
    def __init__(self):
        self.waf = WAFEngine()
        self.ddos = DDoSProtection()
        self.ip_filter = IPFilter()
        self.traffic_analyzer = TrafficAnalyzer()
    
    async def process_request(
        self,
        ip: str,
        url: str,
        method: str,
        headers: Dict[str, str],
        body: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        处理请求
        返回: (是否允许, 原因, 详情)
        """
        details = {
            "ip": ip,
            "checks": []
        }
        
        # 1. IP过滤
        ip_allowed, ip_reason = self.ip_filter.check_ip(ip)
        details["checks"].append({"check": "ip_filter", "result": ip_allowed, "reason": ip_reason})
        
        if not ip_allowed:
            return False, f"IP blocked: {ip_reason}", details
        
        # 2. DDoS防护
        ddos_allowed = self.ddos.record_request(ip)
        details["checks"].append({"check": "ddos", "result": ddos_allowed})
        
        if not ddos_allowed:
            return False, "Rate limited", details
        
        # 3. WAF检查
        waf_action, matched_rules = self.waf.inspect(url, body, headers)
        details["checks"].append({
            "check": "waf",
            "action": waf_action.value,
            "matched_rules": [r.id for r in matched_rules]
        })
        
        if waf_action == WAFAction.BLOCK:
            return False, f"WAF blocked: {matched_rules[0].name if matched_rules else 'unknown'}", details
        
        return True, "allowed", details
    
    def record_response(
        self,
        ip: str,
        path: str,
        method: str,
        response_code: int,
        response_time_ms: float,
        request_size: int = 0,
        response_size: int = 0
    ):
        """记录响应用于分析"""
        self.traffic_analyzer.record_request(
            ip, path, method, response_code,
            response_time_ms, request_size, response_size
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "waf_rules": len(self.waf.rules) + len(self.waf.custom_rules),
            "ddos": self.ddos.get_stats(),
            "traffic": self.traffic_analyzer.get_statistics(),
            "anomalies": self.traffic_analyzer.detect_anomalies()
        }


# FastAPI中间件
class NetworkSecurityMiddleware:
    """网络安全中间件"""
    
    def __init__(self, app, manager: NetworkSecurityManager):
        self.app = app
        self.manager = manager
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        from starlette.requests import Request
        import time
        
        request = Request(scope, receive)
        ip = request.client.host if request.client else "unknown"
        start_time = time.time()
        
        # 获取请求体
        body = ""
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                body = body_bytes.decode()
            except:
                pass
        
        # 处理请求
        allowed, reason, details = await self.manager.process_request(
            ip=ip,
            url=str(request.url),
            method=request.method,
            headers=dict(request.headers),
            body=body
        )
        
        if not allowed:
            response_body = json.dumps({"error": reason}).encode()
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
        
        # 继续处理
        await self.app(scope, receive, send)
        
        # 记录响应
        response_time = (time.time() - start_time) * 1000
        self.manager.record_response(
            ip=ip,
            path=str(request.url.path),
            method=request.method,
            response_code=200,  # 需要从响应获取
            response_time_ms=response_time
        )


import json
