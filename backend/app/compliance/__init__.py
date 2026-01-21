# 地方志数据智能管理系统 - 隐私与合规模块
"""数据隐私保护和合规审计"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import structlog

logger = structlog.get_logger()


class DataCategory(str, Enum):
    """数据类别"""
    PERSONAL = "personal"          # 个人信息
    SENSITIVE = "sensitive"        # 敏感信息
    FINANCIAL = "financial"        # 财务信息
    HEALTH = "health"              # 健康信息
    BIOMETRIC = "biometric"        # 生物特征
    LOCATION = "location"          # 位置信息
    BEHAVIORAL = "behavioral"      # 行为数据
    PUBLIC = "public"              # 公开信息


class LegalBasis(str, Enum):
    """法律依据"""
    CONSENT = "consent"                    # 用户同意
    CONTRACT = "contract"                  # 合同履行
    LEGAL_OBLIGATION = "legal_obligation"  # 法律义务
    VITAL_INTEREST = "vital_interest"      # 重大利益
    PUBLIC_INTEREST = "public_interest"    # 公共利益
    LEGITIMATE_INTEREST = "legitimate_interest"  # 合法利益


class ProcessingPurpose(str, Enum):
    """处理目的"""
    SERVICE_DELIVERY = "service_delivery"   # 服务提供
    ANALYTICS = "analytics"                 # 数据分析
    MARKETING = "marketing"                 # 市场营销
    SECURITY = "security"                   # 安全保护
    LEGAL_COMPLIANCE = "legal_compliance"   # 合规要求
    RESEARCH = "research"                   # 研究


@dataclass
class DataSubjectRight:
    """数据主体权利"""
    right_type: str  # access/rectification/erasure/portability/objection
    user_id: int
    request_time: datetime
    status: str = "pending"  # pending/processing/completed/rejected
    response_time: Optional[datetime] = None
    notes: str = ""


@dataclass
class ConsentRecord:
    """同意记录"""
    user_id: int
    purpose: ProcessingPurpose
    granted: bool
    timestamp: datetime
    ip_address: str = ""
    user_agent: str = ""
    version: str = "1.0"  # 隐私政策版本
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "purpose": self.purpose.value,
            "granted": self.granted,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "version": self.version
        }


class PIIDetector:
    """个人信息检测器"""
    
    # 正则表达式模式
    PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone_cn": r'\b1[3-9]\d{9}\b',
        "id_card_cn": r'\b\d{17}[\dXx]\b',
        "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        "ip_address": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        "passport_cn": r'\b[EeGg]\d{8}\b',
        "bank_account": r'\b\d{16,19}\b',
    }
    
    def __init__(self, patterns: Dict[str, str] = None):
        self.patterns = {**self.PATTERNS, **(patterns or {})}
        self._compiled = {k: re.compile(v) for k, v in self.patterns.items()}
    
    def detect(self, text: str) -> Dict[str, List[str]]:
        """检测文本中的PII"""
        results = {}
        
        for pii_type, pattern in self._compiled.items():
            matches = pattern.findall(text)
            if matches:
                results[pii_type] = matches
        
        return results
    
    def contains_pii(self, text: str) -> bool:
        """检查是否包含PII"""
        return bool(self.detect(text))
    
    def mask(self, text: str, mask_char: str = "*") -> str:
        """脱敏文本中的PII"""
        result = text
        
        for pii_type, pattern in self._compiled.items():
            def replacer(match):
                value = match.group(0)
                if len(value) > 4:
                    return value[:2] + mask_char * (len(value) - 4) + value[-2:]
                return mask_char * len(value)
            
            result = pattern.sub(replacer, result)
        
        return result


class DataAnonymizer:
    """数据匿名化器"""
    
    @staticmethod
    def hash_identifier(value: str, salt: str = "") -> str:
        """哈希标识符"""
        return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:16]
    
    @staticmethod
    def generalize_age(age: int) -> str:
        """泛化年龄"""
        if age < 18:
            return "<18"
        elif age < 25:
            return "18-24"
        elif age < 35:
            return "25-34"
        elif age < 45:
            return "35-44"
        elif age < 55:
            return "45-54"
        elif age < 65:
            return "55-64"
        else:
            return "65+"
    
    @staticmethod
    def generalize_location(location: str) -> str:
        """泛化位置（省级）"""
        # 简化实现：只保留省份
        provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "辽宁",
                    "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西",
                    "山东", "河南", "湖北", "湖南", "广东", "海南", "四川",
                    "贵州", "云南", "陕西", "甘肃", "青海", "台湾", "内蒙古",
                    "广西", "西藏", "宁夏", "新疆", "香港", "澳门"]
        
        for province in provinces:
            if province in location:
                return province
        
        return "未知"
    
    @staticmethod
    def suppress(data: Dict, fields: List[str]) -> Dict:
        """抑制敏感字段"""
        result = data.copy()
        for field in fields:
            if field in result:
                result[field] = "[SUPPRESSED]"
        return result


class ConsentManager:
    """同意管理"""
    
    def __init__(self):
        self.records: Dict[int, List[ConsentRecord]] = {}
    
    def record_consent(
        self,
        user_id: int,
        purpose: ProcessingPurpose,
        granted: bool,
        ip_address: str = "",
        user_agent: str = ""
    ) -> ConsentRecord:
        """记录同意"""
        record = ConsentRecord(
            user_id=user_id,
            purpose=purpose,
            granted=granted,
            timestamp=datetime.now(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if user_id not in self.records:
            self.records[user_id] = []
        self.records[user_id].append(record)
        
        logger.info(
            "记录用户同意",
            user_id=user_id,
            purpose=purpose.value,
            granted=granted
        )
        
        return record
    
    def check_consent(self, user_id: int, purpose: ProcessingPurpose) -> bool:
        """检查用户是否同意"""
        if user_id not in self.records:
            return False
        
        # 获取最新的同意记录
        purpose_records = [
            r for r in self.records[user_id]
            if r.purpose == purpose
        ]
        
        if not purpose_records:
            return False
        
        latest = max(purpose_records, key=lambda x: x.timestamp)
        return latest.granted
    
    def withdraw_consent(self, user_id: int, purpose: ProcessingPurpose):
        """撤回同意"""
        return self.record_consent(user_id, purpose, granted=False)
    
    def get_user_consents(self, user_id: int) -> Dict[str, bool]:
        """获取用户所有同意状态"""
        result = {}
        for purpose in ProcessingPurpose:
            result[purpose.value] = self.check_consent(user_id, purpose)
        return result


class DataRetentionPolicy:
    """数据保留策略"""
    
    # 默认保留期限（天）
    DEFAULT_RETENTION = {
        DataCategory.PERSONAL: 365 * 3,        # 3年
        DataCategory.SENSITIVE: 365,           # 1年
        DataCategory.FINANCIAL: 365 * 7,       # 7年
        DataCategory.HEALTH: 365 * 10,         # 10年
        DataCategory.BEHAVIORAL: 90,           # 90天
        DataCategory.LOCATION: 30,             # 30天
        DataCategory.PUBLIC: -1,               # 永久
    }
    
    def __init__(self, custom_retention: Dict[DataCategory, int] = None):
        self.retention = {**self.DEFAULT_RETENTION, **(custom_retention or {})}
    
    def get_retention_days(self, category: DataCategory) -> int:
        """获取保留天数"""
        return self.retention.get(category, 365)
    
    def is_expired(self, category: DataCategory, created_at: datetime) -> bool:
        """检查是否过期"""
        days = self.get_retention_days(category)
        if days < 0:  # 永久保留
            return False
        
        expiry = created_at + timedelta(days=days)
        return datetime.now() > expiry
    
    def get_expiry_date(self, category: DataCategory, created_at: datetime) -> Optional[datetime]:
        """获取过期日期"""
        days = self.get_retention_days(category)
        if days < 0:
            return None
        return created_at + timedelta(days=days)


class ComplianceChecker:
    """合规检查器"""
    
    def __init__(self):
        self.pii_detector = PIIDetector()
        self.consent_manager = ConsentManager()
        self.retention_policy = DataRetentionPolicy()
    
    def check_data_collection(
        self,
        data: Dict,
        user_id: int,
        purpose: ProcessingPurpose
    ) -> Dict[str, Any]:
        """检查数据收集合规性"""
        issues = []
        
        # 检查同意
        if not self.consent_manager.check_consent(user_id, purpose):
            issues.append({
                "type": "consent_missing",
                "message": f"用户未同意{purpose.value}用途的数据收集"
            })
        
        # 检查PII
        data_str = str(data)
        pii_found = self.pii_detector.detect(data_str)
        if pii_found:
            issues.append({
                "type": "pii_detected",
                "message": f"检测到敏感信息: {list(pii_found.keys())}",
                "details": pii_found
            })
        
        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        }
    
    def audit_data_access(
        self,
        user_id: int,
        accessed_by: int,
        resource_type: str,
        action: str
    ) -> Dict[str, Any]:
        """审计数据访问"""
        return {
            "event": "data_access",
            "user_id": user_id,
            "accessed_by": accessed_by,
            "resource_type": resource_type,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "ip_address": "",  # 从请求上下文获取
            "compliant": True  # 根据策略判断
        }
