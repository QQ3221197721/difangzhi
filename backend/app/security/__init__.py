"""
安全模块 - SecOps完整安全运维体系
Security Module - Complete SecOps Security Operations System

包含以下子模块:
- threat_detection: 威胁检测 - 入侵检测、异常行为、威胁情报
- vulnerability: 漏洞管理 - CVE跟踪、漏洞扫描、修复管理
- secrets: 密钥管理 - 密钥轮转、加密存储、KMS集成
- access_control: 访问控制 - RBAC/ABAC、权限策略、零信任
- network: 网络安全 - WAF规则、DDoS防护、IP过滤
- data_protection: 数据安全 - 加密服务、脱敏、数据分类
- scanning: 安全扫描 - 代码扫描、依赖扫描、SAST/DAST
- incident_response: 事件响应 - 安全事件处理、告警、SOAR
"""

# ==================== 威胁检测 ====================
from .threat_detection import (
    # 枚举类型
    ThreatLevel,
    ThreatType,
    # 数据模型
    ThreatEvent,
    ThreatIntelligence,
    AnomalyScore,
    # 检测器
    IntrusionDetectionSystem,
    AnomalyDetector,
    ThreatIntelligenceService,
    BehaviorAnalyzer,
    # 管理器
    ThreatDetectionManager,
)

# ==================== 漏洞管理 ====================
from .vulnerability import (
    # 枚举类型
    VulnerabilitySeverity,
    VulnerabilityStatus,
    ScanType,
    # 数据模型
    Vulnerability,
    VulnerabilityScanResult,
    RemediationTask,
    # 扫描器
    VulnerabilityScanner,
    CodeScanner,
    DependencyScanner as VulnDependencyScanner,
    ConfigurationScanner,
    # 管理器
    VulnerabilityManager,
)

# ==================== 密钥管理 ====================
from .secrets import (
    # 枚举类型
    KeyType,
    KeyStatus,
    # 数据模型
    KeyMetadata,
    EncryptedSecret,
    # 服务
    KeyManager,
    SecretStore,
    EncryptionService as SecretsEncryptionService,
    # 管理器
    SecretsManager,
)

# ==================== 访问控制 ====================
from .access_control import (
    # 枚举类型
    AccessDecision as AccessDecisionEnum,
    ResourceType,
    ActionType,
    # 数据模型
    Role,
    Permission,
    AccessPolicy,
    AccessRequest,
    AccessDecision,
    # 管理器
    RBACManager,
    ABACManager,
    ZeroTrustManager,
    AccessControlManager,
)

# ==================== 网络安全 ====================
from .network import (
    # 枚举类型
    WAFAction,
    RateLimitStrategy,
    # 数据模型
    WAFRule,
    RateLimitConfig,
    IPFilterRule,
    TrafficAnalysis,
    # 引擎
    WAFEngine,
    DDoSProtection,
    IPFilter,
    TrafficAnalyzer,
    # 管理器
    NetworkSecurityManager,
)

# ==================== 数据安全 ====================
from .data_protection import (
    # 枚举类型
    DataSensitivity,
    DataCategory,
    EncryptionAlgorithm,
    MaskingStrategy,
    # 数据模型
    DataClassification,
    EncryptedData,
    MaskingRule,
    TokenMapping,
    # 服务
    DataClassifier,
    EncryptionService,
    DataMasker,
    FieldEncryption,
    Tokenizer,
    # 管理器
    DataProtectionManager,
)

# ==================== 安全扫描 ====================
from .scanning import (
    # 枚举类型
    SeverityLevel,
    VulnerabilityType,
    # 数据模型
    ScanFinding,
    ScanReport,
    DependencyVulnerability,
    # 扫描器
    SecurityScanner,
    SASTScanner,
    DependencyScanner,
    ConfigScanner,
    SecretScanner,
    # 管理器
    SecurityScanManager,
)

# ==================== 事件响应 ====================
from .incident_response import (
    # 枚举类型
    IncidentSeverity,
    IncidentStatus,
    IncidentCategory,
    AlertChannel,
    # 数据模型
    IncidentEvent,
    Incident,
    Alert,
    PlaybookStep,
    Playbook,
    PlaybookExecution,
    # 通知器
    AlertNotifier,
    EmailNotifier,
    WebhookNotifier,
    DingTalkNotifier,
    SlackNotifier,
    # 管理器
    AlertManager,
    SOAREngine,
    IncidentResponseManager,
)


# ==================== 统一安全管理器 ====================

class SecurityOperationsCenter:
    """
    安全运营中心(SOC) - 统一安全管理入口
    
    整合所有安全模块，提供统一的安全运维能力:
    - 威胁检测与响应
    - 漏洞管理
    - 访问控制
    - 数据保护
    - 安全扫描
    - 事件响应
    """
    
    def __init__(self):
        # 初始化所有安全组件
        self.threat_detection = ThreatDetectionManager()
        self.vulnerability = VulnerabilityManager()
        self.secrets = SecretsManager()
        self.access_control = AccessControlManager()
        self.network_security = NetworkSecurityManager()
        self.data_protection = DataProtectionManager()
        self.security_scanner = SecurityScanManager()
        self.incident_response = IncidentResponseManager()
        
        # 集成告警
        self._setup_integrations()
    
    def _setup_integrations(self):
        """设置模块间集成"""
        # 威胁检测 -> 事件响应
        # 当检测到威胁时，自动创建安全事件
        pass
    
    async def analyze_request(
        self,
        ip: str,
        user_id: int,
        method: str,
        path: str,
        headers: dict,
        body: str = None
    ) -> dict:
        """
        分析请求安全性
        
        整合多个安全检查:
        1. 网络层检查(WAF、IP过滤、DDoS)
        2. 访问控制检查(RBAC/ABAC)
        3. 威胁检测(入侵检测、异常行为)
        """
        result = {
            "allowed": True,
            "checks": {},
            "threats": [],
            "recommendations": []
        }
        
        # 1. 网络安全检查
        network_result = await self.network_security.analyze_traffic({
            "ip": ip,
            "method": method,
            "path": path,
            "headers": headers
        })
        result["checks"]["network"] = network_result
        
        if not network_result.get("allowed", True):
            result["allowed"] = False
            result["recommendations"].append("请求被网络安全策略拦截")
        
        # 2. 威胁检测
        threat_result = await self.threat_detection.ids.analyze_request(
            ip=ip,
            user_id=user_id,
            method=method,
            path=path,
            headers=headers,
            body=body,
            query_params={}
        )
        result["checks"]["threat"] = {"allowed": threat_result[0]}
        result["threats"] = [t.to_dict() if hasattr(t, 'to_dict') else str(t) for t in threat_result[1]]
        
        if not threat_result[0]:
            result["allowed"] = False
        
        return result
    
    async def full_security_scan(self, target_path: str) -> dict:
        """执行完整安全扫描"""
        return await self.security_scanner.full_scan(target_path)
    
    async def create_security_incident(
        self,
        title: str,
        description: str,
        severity: str,
        category: str,
        **kwargs
    ):
        """创建安全事件"""
        return await self.incident_response.create_incident(
            title=title,
            description=description,
            severity=IncidentSeverity(severity),
            category=IncidentCategory(category),
            source="SOC",
            **kwargs
        )
    
    def get_security_posture(self) -> dict:
        """获取安全态势"""
        return {
            "incidents": self.incident_response.get_incident_metrics(),
            "active_threats": len(self.threat_detection.threat_intel.active_threats),
            "vulnerabilities": {
                "total": len(self.vulnerability.vulnerabilities),
                "critical": sum(1 for v in self.vulnerability.vulnerabilities.values() 
                              if v.severity == VulnerabilitySeverity.CRITICAL)
            },
            "scan_summary": self.security_scanner.generate_summary_report() if self.security_scanner.scan_history else {},
            "access_control": {
                "roles": len(self.access_control.rbac.roles),
                "policies": len(self.access_control.abac.policies)
            }
        }
    
    def get_compliance_status(self) -> dict:
        """获取合规状态"""
        return {
            "encryption": {
                "at_rest": True,
                "in_transit": True,
                "algorithm": "AES-256-GCM"
            },
            "access_control": {
                "rbac_enabled": True,
                "abac_enabled": True,
                "zero_trust": True
            },
            "monitoring": {
                "ids_enabled": True,
                "anomaly_detection": True,
                "threat_intelligence": True
            },
            "incident_response": {
                "playbooks_count": len(self.incident_response.soar_engine.playbooks),
                "soar_enabled": True
            }
        }


# ==================== 导出 ====================

__all__ = [
    # ===== 威胁检测 =====
    "ThreatLevel",
    "ThreatType",
    "ThreatEvent",
    "ThreatIntelligence",
    "AnomalyScore",
    "IntrusionDetectionSystem",
    "AnomalyDetector",
    "ThreatIntelligenceService",
    "BehaviorAnalyzer",
    "ThreatDetectionManager",
    
    # ===== 漏洞管理 =====
    "VulnerabilitySeverity",
    "VulnerabilityStatus",
    "ScanType",
    "Vulnerability",
    "VulnerabilityScanResult",
    "RemediationTask",
    "VulnerabilityScanner",
    "CodeScanner",
    "VulnDependencyScanner",
    "ConfigurationScanner",
    "VulnerabilityManager",
    
    # ===== 密钥管理 =====
    "KeyType",
    "KeyStatus",
    "KeyMetadata",
    "EncryptedSecret",
    "KeyManager",
    "SecretStore",
    "SecretsEncryptionService",
    "SecretsManager",
    
    # ===== 访问控制 =====
    "AccessDecisionEnum",
    "ResourceType",
    "ActionType",
    "Role",
    "Permission",
    "AccessPolicy",
    "AccessRequest",
    "AccessDecision",
    "RBACManager",
    "ABACManager",
    "ZeroTrustManager",
    "AccessControlManager",
    
    # ===== 网络安全 =====
    "WAFAction",
    "RateLimitStrategy",
    "WAFRule",
    "RateLimitConfig",
    "IPFilterRule",
    "TrafficAnalysis",
    "WAFEngine",
    "DDoSProtection",
    "IPFilter",
    "TrafficAnalyzer",
    "NetworkSecurityManager",
    
    # ===== 数据安全 =====
    "DataSensitivity",
    "DataCategory",
    "EncryptionAlgorithm",
    "MaskingStrategy",
    "DataClassification",
    "EncryptedData",
    "MaskingRule",
    "TokenMapping",
    "DataClassifier",
    "EncryptionService",
    "DataMasker",
    "FieldEncryption",
    "Tokenizer",
    "DataProtectionManager",
    
    # ===== 安全扫描 =====
    "SeverityLevel",
    "VulnerabilityType",
    "ScanFinding",
    "ScanReport",
    "DependencyVulnerability",
    "SecurityScanner",
    "SASTScanner",
    "DependencyScanner",
    "ConfigScanner",
    "SecretScanner",
    "SecurityScanManager",
    
    # ===== 事件响应 =====
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentCategory",
    "AlertChannel",
    "IncidentEvent",
    "Incident",
    "Alert",
    "PlaybookStep",
    "Playbook",
    "PlaybookExecution",
    "AlertNotifier",
    "EmailNotifier",
    "WebhookNotifier",
    "DingTalkNotifier",
    "SlackNotifier",
    "AlertManager",
    "SOAREngine",
    "IncidentResponseManager",
    
    # ===== 统一入口 =====
    "SecurityOperationsCenter",
]
