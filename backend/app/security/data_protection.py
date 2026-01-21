"""
数据安全模块 - 加密服务、脱敏、数据分类
Data Protection Module - Encryption, Masking, Data Classification
"""

import hashlib
import hmac
import re
import secrets
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Union
import json
import logging
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


logger = logging.getLogger(__name__)


# ==================== 数据分类 ====================

class DataSensitivity(str, Enum):
    """数据敏感级别"""
    PUBLIC = "public"              # 公开数据
    INTERNAL = "internal"          # 内部数据
    CONFIDENTIAL = "confidential"  # 机密数据
    RESTRICTED = "restricted"      # 受限数据
    TOP_SECRET = "top_secret"      # 绝密数据


class DataCategory(str, Enum):
    """数据类别"""
    PII = "pii"                    # 个人身份信息
    PHI = "phi"                    # 健康信息
    PCI = "pci"                    # 支付卡信息
    CREDENTIALS = "credentials"    # 凭证信息
    FINANCIAL = "financial"        # 财务信息
    HISTORICAL = "historical"      # 历史档案
    RESEARCH = "research"          # 研究数据
    SYSTEM = "system"              # 系统数据


@dataclass
class DataClassification:
    """数据分类结果"""
    sensitivity: DataSensitivity
    categories: List[DataCategory]
    confidence: float
    detected_patterns: List[str]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


class DataClassifier:
    """数据分类器"""
    
    # PII模式
    PII_PATTERNS = {
        "id_card": r"\b[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",
        "phone": r"\b1[3-9]\d{9}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "bank_card": r"\b[1-9]\d{15,18}\b",
        "passport": r"\b[GgEe]\d{8}\b|[a-zA-Z]\d{9}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "mac_address": r"\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b",
    }
    
    # 凭证模式
    CREDENTIAL_PATTERNS = {
        "api_key": r"(?i)(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{20,})",
        "password": r"(?i)(password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,})",
        "secret": r"(?i)(secret|token)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{16,})",
        "private_key": r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        "jwt": r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_.+/]*",
    }
    
    # 财务模式
    FINANCIAL_PATTERNS = {
        "amount": r"(?i)(金额|amount|price|cost)['\"]?\s*[:=]\s*[\d,.]+",
        "account": r"(?i)(账[号户]|account)['\"]?\s*[:=]\s*\d+",
    }
    
    # 历史档案模式
    HISTORICAL_PATTERNS = {
        "dynasty": r"(清|明|元|宋|唐|隋|晋|汉|秦|周|商|夏)(朝|代|初|末|中)",
        "era_name": r"(康熙|雍正|乾隆|嘉庆|道光|咸丰|同治|光绪|宣统|洪武|永乐|宣德|万历)[\d一二三四五六七八九十]+年",
        "county_record": r"(县志|府志|州志|省志|通志|方志)",
        "ancient_title": r"(知县|知府|布政使|巡抚|总督|提督)",
    }
    
    def __init__(self):
        self.compiled_patterns: Dict[str, Dict[str, re.Pattern]] = {}
        self._compile_patterns()
        
    def _compile_patterns(self):
        """编译正则表达式"""
        pattern_groups = {
            "pii": self.PII_PATTERNS,
            "credential": self.CREDENTIAL_PATTERNS,
            "financial": self.FINANCIAL_PATTERNS,
            "historical": self.HISTORICAL_PATTERNS,
        }
        
        for group, patterns in pattern_groups.items():
            self.compiled_patterns[group] = {
                name: re.compile(pattern)
                for name, pattern in patterns.items()
            }
    
    def classify(self, data: Union[str, Dict, List]) -> DataClassification:
        """分类数据"""
        # 转换为字符串进行分析
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False)
        elif isinstance(data, list):
            text = json.dumps(data, ensure_ascii=False)
        else:
            text = str(data)
        
        detected = []
        categories = set()
        
        # 检测各类模式
        for group, patterns in self.compiled_patterns.items():
            for name, pattern in patterns.items():
                if pattern.search(text):
                    detected.append(f"{group}:{name}")
                    
                    if group == "pii":
                        categories.add(DataCategory.PII)
                    elif group == "credential":
                        categories.add(DataCategory.CREDENTIALS)
                    elif group == "financial":
                        categories.add(DataCategory.FINANCIAL)
                    elif group == "historical":
                        categories.add(DataCategory.HISTORICAL)
        
        # 确定敏感级别
        sensitivity = self._determine_sensitivity(categories, detected)
        
        # 生成建议
        recommendations = self._generate_recommendations(sensitivity, categories)
        
        # 计算置信度
        confidence = min(len(detected) * 0.15 + 0.5, 1.0) if detected else 0.3
        
        return DataClassification(
            sensitivity=sensitivity,
            categories=list(categories),
            confidence=confidence,
            detected_patterns=detected,
            recommendations=recommendations
        )
    
    def _determine_sensitivity(
        self,
        categories: Set[DataCategory],
        detected: List[str]
    ) -> DataSensitivity:
        """确定敏感级别"""
        if DataCategory.CREDENTIALS in categories:
            return DataSensitivity.TOP_SECRET
        
        if "credential:private_key" in detected:
            return DataSensitivity.TOP_SECRET
        
        if DataCategory.PII in categories:
            if any("id_card" in d or "bank_card" in d for d in detected):
                return DataSensitivity.RESTRICTED
            return DataSensitivity.CONFIDENTIAL
        
        if DataCategory.FINANCIAL in categories:
            return DataSensitivity.CONFIDENTIAL
        
        if DataCategory.HISTORICAL in categories:
            return DataSensitivity.INTERNAL
        
        return DataSensitivity.PUBLIC
    
    def _generate_recommendations(
        self,
        sensitivity: DataSensitivity,
        categories: Set[DataCategory]
    ) -> List[str]:
        """生成数据保护建议"""
        recommendations = []
        
        if sensitivity == DataSensitivity.TOP_SECRET:
            recommendations.extend([
                "使用HSM存储密钥",
                "启用全链路加密",
                "限制访问仅限必要人员",
                "启用审计日志"
            ])
        elif sensitivity == DataSensitivity.RESTRICTED:
            recommendations.extend([
                "使用AES-256加密存储",
                "启用访问控制",
                "定期审计访问记录"
            ])
        elif sensitivity == DataSensitivity.CONFIDENTIAL:
            recommendations.extend([
                "加密存储",
                "传输时使用TLS"
            ])
        
        if DataCategory.PII in categories:
            recommendations.append("考虑数据脱敏处理")
        
        return recommendations


# ==================== 加密服务 ====================

class EncryptionAlgorithm(str, Enum):
    """加密算法"""
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"
    FERNET = "fernet"


@dataclass
class EncryptedData:
    """加密数据"""
    ciphertext: bytes
    algorithm: EncryptionAlgorithm
    iv: Optional[bytes] = None
    tag: Optional[bytes] = None
    salt: Optional[bytes] = None
    key_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "algorithm": self.algorithm.value,
            "iv": base64.b64encode(self.iv).decode() if self.iv else None,
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
            "salt": base64.b64encode(self.salt).decode() if self.salt else None,
            "key_id": self.key_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "EncryptedData":
        """从字典创建"""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            algorithm=EncryptionAlgorithm(data["algorithm"]),
            iv=base64.b64decode(data["iv"]) if data.get("iv") else None,
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
            salt=base64.b64decode(data["salt"]) if data.get("salt") else None,
            key_id=data.get("key_id"),
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class EncryptionService:
    """加密服务"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        self.master_key = master_key or secrets.token_bytes(32)
        self._key_cache: Dict[str, bytes] = {}
        
    def derive_key(
        self,
        password: str,
        salt: Optional[bytes] = None,
        iterations: int = 100000
    ) -> Tuple[bytes, bytes]:
        """从密码派生密钥"""
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        return key, salt
    
    def encrypt(
        self,
        plaintext: Union[str, bytes],
        key: Optional[bytes] = None,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        key_id: Optional[str] = None
    ) -> EncryptedData:
        """加密数据"""
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        
        key = key or self.master_key
        
        if algorithm == EncryptionAlgorithm.FERNET:
            return self._encrypt_fernet(plaintext, key, key_id)
        elif algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self._encrypt_aes_gcm(plaintext, key, key_id)
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            return self._encrypt_aes_cbc(plaintext, key, key_id)
        else:
            raise ValueError(f"不支持的加密算法: {algorithm}")
    
    def decrypt(
        self,
        encrypted: EncryptedData,
        key: Optional[bytes] = None
    ) -> bytes:
        """解密数据"""
        key = key or self.master_key
        
        if encrypted.algorithm == EncryptionAlgorithm.FERNET:
            return self._decrypt_fernet(encrypted, key)
        elif encrypted.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self._decrypt_aes_gcm(encrypted, key)
        elif encrypted.algorithm == EncryptionAlgorithm.AES_256_CBC:
            return self._decrypt_aes_cbc(encrypted, key)
        else:
            raise ValueError(f"不支持的解密算法: {encrypted.algorithm}")
    
    def _encrypt_fernet(
        self,
        plaintext: bytes,
        key: bytes,
        key_id: Optional[str]
    ) -> EncryptedData:
        """Fernet加密"""
        # Fernet需要32字节base64编码的密钥
        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)
        ciphertext = f.encrypt(plaintext)
        
        return EncryptedData(
            ciphertext=ciphertext,
            algorithm=EncryptionAlgorithm.FERNET,
            key_id=key_id
        )
    
    def _decrypt_fernet(self, encrypted: EncryptedData, key: bytes) -> bytes:
        """Fernet解密"""
        fernet_key = base64.urlsafe_b64encode(key[:32])
        f = Fernet(fernet_key)
        return f.decrypt(encrypted.ciphertext)
    
    def _encrypt_aes_gcm(
        self,
        plaintext: bytes,
        key: bytes,
        key_id: Optional[str]
    ) -> EncryptedData:
        """AES-256-GCM加密"""
        iv = secrets.token_bytes(12)
        cipher = Cipher(
            algorithms.AES(key[:32]),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        return EncryptedData(
            ciphertext=ciphertext,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            iv=iv,
            tag=encryptor.tag,
            key_id=key_id
        )
    
    def _decrypt_aes_gcm(self, encrypted: EncryptedData, key: bytes) -> bytes:
        """AES-256-GCM解密"""
        cipher = Cipher(
            algorithms.AES(key[:32]),
            modes.GCM(encrypted.iv, encrypted.tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted.ciphertext) + decryptor.finalize()
    
    def _encrypt_aes_cbc(
        self,
        plaintext: bytes,
        key: bytes,
        key_id: Optional[str]
    ) -> EncryptedData:
        """AES-256-CBC加密"""
        iv = secrets.token_bytes(16)
        
        # PKCS7填充
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()
        
        cipher = Cipher(
            algorithms.AES(key[:32]),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return EncryptedData(
            ciphertext=ciphertext,
            algorithm=EncryptionAlgorithm.AES_256_CBC,
            iv=iv,
            key_id=key_id
        )
    
    def _decrypt_aes_cbc(self, encrypted: EncryptedData, key: bytes) -> bytes:
        """AES-256-CBC解密"""
        cipher = Cipher(
            algorithms.AES(key[:32]),
            modes.CBC(encrypted.iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted.ciphertext) + decryptor.finalize()
        
        # 移除填充
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()
    
    def hash_data(
        self,
        data: Union[str, bytes],
        algorithm: str = "sha256"
    ) -> str:
        """计算哈希"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        if algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(data).hexdigest()
        elif algorithm == "blake2b":
            return hashlib.blake2b(data).hexdigest()
        else:
            raise ValueError(f"不支持的哈希算法: {algorithm}")
    
    def hmac_sign(
        self,
        data: Union[str, bytes],
        key: Optional[bytes] = None
    ) -> str:
        """HMAC签名"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        key = key or self.master_key
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    
    def hmac_verify(
        self,
        data: Union[str, bytes],
        signature: str,
        key: Optional[bytes] = None
    ) -> bool:
        """验证HMAC签名"""
        expected = self.hmac_sign(data, key)
        return hmac.compare_digest(expected, signature)


# ==================== 数据脱敏 ====================

class MaskingStrategy(str, Enum):
    """脱敏策略"""
    FULL = "full"           # 完全遮蔽
    PARTIAL = "partial"     # 部分遮蔽
    HASH = "hash"           # 哈希脱敏
    PSEUDONYM = "pseudonym" # 假名化
    TRUNCATE = "truncate"   # 截断
    GENERALIZE = "generalize"  # 泛化


@dataclass
class MaskingRule:
    """脱敏规则"""
    field_name: str
    strategy: MaskingStrategy
    pattern: Optional[str] = None
    replacement: str = "*"
    preserve_length: bool = True
    preserve_prefix: int = 0
    preserve_suffix: int = 0


class DataMasker:
    """数据脱敏器"""
    
    DEFAULT_RULES = [
        MaskingRule("id_card", MaskingStrategy.PARTIAL, preserve_prefix=6, preserve_suffix=4),
        MaskingRule("phone", MaskingStrategy.PARTIAL, preserve_prefix=3, preserve_suffix=4),
        MaskingRule("email", MaskingStrategy.PARTIAL, preserve_prefix=2, preserve_suffix=0),
        MaskingRule("bank_card", MaskingStrategy.PARTIAL, preserve_prefix=4, preserve_suffix=4),
        MaskingRule("name", MaskingStrategy.PARTIAL, preserve_prefix=1, preserve_suffix=0),
        MaskingRule("password", MaskingStrategy.FULL),
        MaskingRule("api_key", MaskingStrategy.PARTIAL, preserve_prefix=4, preserve_suffix=4),
    ]
    
    def __init__(self, rules: Optional[List[MaskingRule]] = None):
        self.rules = {r.field_name: r for r in (rules or self.DEFAULT_RULES)}
        self._pseudonym_map: Dict[str, str] = {}
        self._pseudonym_counter = 0
    
    def mask(
        self,
        value: str,
        rule: MaskingRule
    ) -> str:
        """应用脱敏规则"""
        if not value:
            return value
        
        if rule.strategy == MaskingStrategy.FULL:
            return self._full_mask(value, rule)
        elif rule.strategy == MaskingStrategy.PARTIAL:
            return self._partial_mask(value, rule)
        elif rule.strategy == MaskingStrategy.HASH:
            return self._hash_mask(value)
        elif rule.strategy == MaskingStrategy.PSEUDONYM:
            return self._pseudonym_mask(value)
        elif rule.strategy == MaskingStrategy.TRUNCATE:
            return self._truncate_mask(value, rule)
        elif rule.strategy == MaskingStrategy.GENERALIZE:
            return self._generalize_mask(value, rule)
        
        return value
    
    def _full_mask(self, value: str, rule: MaskingRule) -> str:
        """完全遮蔽"""
        if rule.preserve_length:
            return rule.replacement * len(value)
        return rule.replacement * 8
    
    def _partial_mask(self, value: str, rule: MaskingRule) -> str:
        """部分遮蔽"""
        if len(value) <= rule.preserve_prefix + rule.preserve_suffix:
            return rule.replacement * len(value)
        
        prefix = value[:rule.preserve_prefix] if rule.preserve_prefix > 0 else ""
        suffix = value[-rule.preserve_suffix:] if rule.preserve_suffix > 0 else ""
        middle_len = len(value) - rule.preserve_prefix - rule.preserve_suffix
        
        if rule.preserve_length:
            middle = rule.replacement * middle_len
        else:
            middle = rule.replacement * 4
        
        return prefix + middle + suffix
    
    def _hash_mask(self, value: str) -> str:
        """哈希脱敏"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    def _pseudonym_mask(self, value: str) -> str:
        """假名化"""
        if value not in self._pseudonym_map:
            self._pseudonym_counter += 1
            self._pseudonym_map[value] = f"ANON_{self._pseudonym_counter:06d}"
        return self._pseudonym_map[value]
    
    def _truncate_mask(self, value: str, rule: MaskingRule) -> str:
        """截断"""
        return value[:rule.preserve_prefix] if rule.preserve_prefix > 0 else ""
    
    def _generalize_mask(self, value: str, rule: MaskingRule) -> str:
        """泛化"""
        # 对于数字，返回范围
        try:
            num = int(value)
            bucket = (num // 10) * 10
            return f"{bucket}-{bucket + 9}"
        except ValueError:
            # 对于字符串，返回类别
            return f"[{len(value)}字符]"
    
    def mask_dict(
        self,
        data: Dict[str, Any],
        field_rules: Optional[Dict[str, MaskingRule]] = None
    ) -> Dict[str, Any]:
        """脱敏字典数据"""
        rules = field_rules or self.rules
        result = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self.mask_dict(value, rules)
            elif isinstance(value, list):
                result[key] = [
                    self.mask_dict(v, rules) if isinstance(v, dict) else v
                    for v in value
                ]
            elif key in rules and isinstance(value, str):
                result[key] = self.mask(value, rules[key])
            else:
                result[key] = value
        
        return result
    
    def mask_text(self, text: str) -> str:
        """脱敏文本中的敏感信息"""
        result = text
        
        # 身份证脱敏
        id_pattern = r'\b[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b'
        result = re.sub(id_pattern, lambda m: m.group()[:6] + "****" + m.group()[-4:], result)
        
        # 手机号脱敏
        phone_pattern = r'\b1[3-9]\d{9}\b'
        result = re.sub(phone_pattern, lambda m: m.group()[:3] + "****" + m.group()[-4:], result)
        
        # 邮箱脱敏
        email_pattern = r'\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'
        result = re.sub(email_pattern, lambda m: m.group(1)[:2] + "****@" + m.group(2), result)
        
        # 银行卡脱敏
        bank_pattern = r'\b[1-9]\d{15,18}\b'
        result = re.sub(bank_pattern, lambda m: m.group()[:4] + "****" + m.group()[-4:], result)
        
        return result


# ==================== 字段级加密 ====================

class FieldEncryption:
    """字段级加密"""
    
    def __init__(self, encryption_service: EncryptionService):
        self.encryption_service = encryption_service
        self.encrypted_fields: Set[str] = set()
    
    def encrypt_field(
        self,
        value: Any,
        field_name: str,
        key: Optional[bytes] = None
    ) -> str:
        """加密字段值"""
        if value is None:
            return None
        
        # 序列化
        if isinstance(value, (dict, list)):
            plaintext = json.dumps(value, ensure_ascii=False)
        else:
            plaintext = str(value)
        
        # 加密
        encrypted = self.encryption_service.encrypt(plaintext, key)
        
        # 返回Base64编码
        return base64.b64encode(json.dumps(encrypted.to_dict()).encode()).decode()
    
    def decrypt_field(
        self,
        encrypted_value: str,
        field_name: str,
        key: Optional[bytes] = None
    ) -> Any:
        """解密字段值"""
        if not encrypted_value:
            return None
        
        try:
            # 解码
            data = json.loads(base64.b64decode(encrypted_value))
            encrypted = EncryptedData.from_dict(data)
            
            # 解密
            plaintext = self.encryption_service.decrypt(encrypted, key)
            return plaintext.decode('utf-8')
        except Exception as e:
            logger.error(f"解密字段失败: {field_name}, 错误: {e}")
            raise
    
    def encrypt_record(
        self,
        record: Dict[str, Any],
        fields_to_encrypt: List[str],
        key: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """加密记录中的指定字段"""
        result = record.copy()
        
        for field in fields_to_encrypt:
            if field in result:
                result[field] = self.encrypt_field(result[field], field, key)
        
        return result
    
    def decrypt_record(
        self,
        record: Dict[str, Any],
        fields_to_decrypt: List[str],
        key: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """解密记录中的指定字段"""
        result = record.copy()
        
        for field in fields_to_decrypt:
            if field in result:
                result[field] = self.decrypt_field(result[field], field, key)
        
        return result


# ==================== 令牌化 ====================

@dataclass
class TokenMapping:
    """令牌映射"""
    token: str
    original_hash: str
    created_at: datetime
    expires_at: Optional[datetime]
    scope: str


class Tokenizer:
    """数据令牌化服务"""
    
    def __init__(self, encryption_service: EncryptionService):
        self.encryption_service = encryption_service
        self._token_vault: Dict[str, bytes] = {}  # token -> encrypted_data
        self._hash_to_token: Dict[str, str] = {}  # hash -> token
    
    def tokenize(
        self,
        value: str,
        scope: str = "default",
        ttl_hours: Optional[int] = None
    ) -> str:
        """令牌化敏感数据"""
        # 计算哈希用于去重
        value_hash = self.encryption_service.hash_data(value)
        
        # 检查是否已存在令牌
        if value_hash in self._hash_to_token:
            return self._hash_to_token[value_hash]
        
        # 生成令牌
        token = f"TKN_{secrets.token_hex(16)}"
        
        # 加密原始值
        encrypted = self.encryption_service.encrypt(value)
        self._token_vault[token] = encrypted.ciphertext
        self._hash_to_token[value_hash] = token
        
        return token
    
    def detokenize(self, token: str) -> Optional[str]:
        """还原令牌"""
        if token not in self._token_vault:
            return None
        
        encrypted = EncryptedData(
            ciphertext=self._token_vault[token],
            algorithm=EncryptionAlgorithm.FERNET
        )
        
        try:
            return self.encryption_service.decrypt(encrypted).decode('utf-8')
        except Exception:
            return None
    
    def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        if token in self._token_vault:
            del self._token_vault[token]
            # 清理哈希映射
            self._hash_to_token = {
                h: t for h, t in self._hash_to_token.items()
                if t != token
            }
            return True
        return False


# ==================== 数据保护管理器 ====================

class DataProtectionManager:
    """数据保护管理器 - 统一接口"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        self.encryption = EncryptionService(master_key)
        self.classifier = DataClassifier()
        self.masker = DataMasker()
        self.field_encryption = FieldEncryption(self.encryption)
        self.tokenizer = Tokenizer(self.encryption)
        
    def protect(
        self,
        data: Union[str, Dict, List],
        auto_classify: bool = True
    ) -> Dict[str, Any]:
        """智能数据保护"""
        # 分类
        if auto_classify:
            classification = self.classifier.classify(data)
        else:
            classification = None
        
        # 根据敏感级别决定保护策略
        if classification:
            if classification.sensitivity == DataSensitivity.TOP_SECRET:
                # 最高级别：加密
                if isinstance(data, str):
                    protected = self.encryption.encrypt(data).to_dict()
                else:
                    protected = self.encryption.encrypt(
                        json.dumps(data, ensure_ascii=False)
                    ).to_dict()
                protection_method = "encryption"
            elif classification.sensitivity in [
                DataSensitivity.RESTRICTED,
                DataSensitivity.CONFIDENTIAL
            ]:
                # 高级别：脱敏
                if isinstance(data, dict):
                    protected = self.masker.mask_dict(data)
                elif isinstance(data, str):
                    protected = self.masker.mask_text(data)
                else:
                    protected = data
                protection_method = "masking"
            else:
                protected = data
                protection_method = "none"
        else:
            protected = data
            protection_method = "none"
        
        return {
            "data": protected,
            "classification": classification.__dict__ if classification else None,
            "protection_method": protection_method
        }
    
    def encrypt_sensitive_fields(
        self,
        record: Dict[str, Any],
        sensitive_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """加密记录中的敏感字段"""
        if sensitive_fields is None:
            # 自动检测敏感字段
            sensitive_fields = []
            for key, value in record.items():
                if isinstance(value, str):
                    classification = self.classifier.classify(value)
                    if classification.sensitivity in [
                        DataSensitivity.TOP_SECRET,
                        DataSensitivity.RESTRICTED
                    ]:
                        sensitive_fields.append(key)
        
        return self.field_encryption.encrypt_record(record, sensitive_fields)
    
    def create_safe_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建安全的日志数据（自动脱敏）"""
        return self.masker.mask_dict(data)
    
    def get_data_summary(self, data: Union[str, Dict, List]) -> Dict[str, Any]:
        """获取数据摘要（不暴露敏感信息）"""
        classification = self.classifier.classify(data)
        
        return {
            "sensitivity": classification.sensitivity.value,
            "categories": [c.value for c in classification.categories],
            "size": len(str(data)),
            "confidence": classification.confidence,
            "recommendations": classification.recommendations
        }


# ==================== 导出 ====================

__all__ = [
    # 数据分类
    "DataSensitivity",
    "DataCategory",
    "DataClassification",
    "DataClassifier",
    # 加密服务
    "EncryptionAlgorithm",
    "EncryptedData",
    "EncryptionService",
    # 数据脱敏
    "MaskingStrategy",
    "MaskingRule",
    "DataMasker",
    # 字段加密
    "FieldEncryption",
    # 令牌化
    "TokenMapping",
    "Tokenizer",
    # 统一管理
    "DataProtectionManager",
]
