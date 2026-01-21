# 地方志数据智能管理系统 - 密钥管理
"""密钥轮转、加密存储、KMS集成"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import structlog

logger = structlog.get_logger()


class KeyType(str, Enum):
    """密钥类型"""
    SYMMETRIC = "symmetric"       # 对称密钥
    ASYMMETRIC = "asymmetric"     # 非对称密钥
    SIGNING = "signing"           # 签名密钥
    ENCRYPTION = "encryption"     # 加密密钥
    API_KEY = "api_key"           # API密钥
    JWT_SECRET = "jwt_secret"     # JWT密钥


class KeyStatus(str, Enum):
    """密钥状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    COMPROMISED = "compromised"
    PENDING_ROTATION = "pending_rotation"


@dataclass
class KeyMetadata:
    """密钥元数据"""
    key_id: str
    key_type: KeyType
    status: KeyStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    rotated_at: Optional[datetime] = None
    version: int = 1
    algorithm: str = "AES-256"
    purpose: str = ""
    tags: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict:
        return {
            "key_id": self.key_id,
            "key_type": self.key_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "rotated_at": self.rotated_at.isoformat() if self.rotated_at else None,
            "version": self.version,
            "algorithm": self.algorithm,
            "purpose": self.purpose,
            "tags": self.tags
        }


class KeyDerivation:
    """密钥派生"""
    
    @staticmethod
    def derive_key(
        password: str,
        salt: bytes = None,
        iterations: int = 100000,
        key_length: int = 32
    ) -> Tuple[bytes, bytes]:
        """从密码派生密钥"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        return key, salt
    
    @staticmethod
    def derive_key_hkdf(
        master_key: bytes,
        context: str,
        length: int = 32
    ) -> bytes:
        """使用HKDF派生密钥"""
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=None,
            info=context.encode(),
            backend=default_backend()
        )
        return hkdf.derive(master_key)


class EncryptionService:
    """加密服务"""
    
    def __init__(self, master_key: bytes = None):
        if master_key is None:
            master_key = os.urandom(32)
        
        self._master_key = master_key
        self._fernet = Fernet(base64.urlsafe_b64encode(master_key[:32].ljust(32, b'\0')))
    
    def encrypt(self, plaintext: str) -> str:
        """加密文本"""
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """解密文本"""
        return self._fernet.decrypt(ciphertext.encode()).decode()
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        """加密字节数据"""
        return self._fernet.encrypt(data)
    
    def decrypt_bytes(self, data: bytes) -> bytes:
        """解密字节数据"""
        return self._fernet.decrypt(data)
    
    @staticmethod
    def generate_aes_key() -> bytes:
        """生成AES密钥"""
        return os.urandom(32)
    
    @staticmethod
    def generate_rsa_keypair(key_size: int = 2048) -> Tuple[bytes, bytes]:
        """生成RSA密钥对"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return private_pem, public_pem


class SecretStore(ABC):
    """密钥存储抽象基类"""
    
    @abstractmethod
    async def get_secret(self, key_id: str) -> Optional[str]:
        pass
    
    @abstractmethod
    async def set_secret(self, key_id: str, value: str, metadata: KeyMetadata):
        pass
    
    @abstractmethod
    async def delete_secret(self, key_id: str):
        pass
    
    @abstractmethod
    async def list_secrets(self) -> List[KeyMetadata]:
        pass


class FileSecretStore(SecretStore):
    """文件密钥存储（加密存储）"""
    
    def __init__(
        self,
        storage_path: str = "data/secrets",
        master_password: str = None
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 主密钥
        if master_password:
            self._master_key, self._salt = KeyDerivation.derive_key(master_password)
        else:
            self._master_key = os.urandom(32)
            self._salt = os.urandom(16)
        
        self._encryption = EncryptionService(self._master_key)
        self._metadata: Dict[str, KeyMetadata] = {}
        self._load_metadata()
    
    def _load_metadata(self):
        """加载元数据"""
        meta_file = self.storage_path / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        meta = KeyMetadata(
                            key_id=item["key_id"],
                            key_type=KeyType(item["key_type"]),
                            status=KeyStatus(item["status"]),
                            created_at=datetime.fromisoformat(item["created_at"]),
                            expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
                            version=item.get("version", 1),
                            algorithm=item.get("algorithm", "AES-256"),
                            purpose=item.get("purpose", "")
                        )
                        self._metadata[meta.key_id] = meta
            except Exception as e:
                logger.error("加载密钥元数据失败", error=str(e))
    
    def _save_metadata(self):
        """保存元数据"""
        meta_file = self.storage_path / "metadata.json"
        with open(meta_file, "w") as f:
            json.dump([m.to_dict() for m in self._metadata.values()], f, indent=2)
    
    async def get_secret(self, key_id: str) -> Optional[str]:
        """获取密钥"""
        secret_file = self.storage_path / f"{key_id}.enc"
        if not secret_file.exists():
            return None
        
        try:
            with open(secret_file, "r") as f:
                encrypted = f.read()
            return self._encryption.decrypt(encrypted)
        except Exception as e:
            logger.error("获取密钥失败", key_id=key_id, error=str(e))
            return None
    
    async def set_secret(self, key_id: str, value: str, metadata: KeyMetadata):
        """设置密钥"""
        secret_file = self.storage_path / f"{key_id}.enc"
        
        encrypted = self._encryption.encrypt(value)
        with open(secret_file, "w") as f:
            f.write(encrypted)
        
        self._metadata[key_id] = metadata
        self._save_metadata()
        
        logger.info("密钥已存储", key_id=key_id, key_type=metadata.key_type.value)
    
    async def delete_secret(self, key_id: str):
        """删除密钥"""
        secret_file = self.storage_path / f"{key_id}.enc"
        if secret_file.exists():
            secret_file.unlink()
        
        self._metadata.pop(key_id, None)
        self._save_metadata()
    
    async def list_secrets(self) -> List[KeyMetadata]:
        """列出所有密钥"""
        return list(self._metadata.values())


class KeyRotationPolicy:
    """密钥轮转策略"""
    
    def __init__(
        self,
        rotation_interval_days: int = 90,
        grace_period_days: int = 7,
        max_versions: int = 3
    ):
        self.rotation_interval = timedelta(days=rotation_interval_days)
        self.grace_period = timedelta(days=grace_period_days)
        self.max_versions = max_versions
    
    def needs_rotation(self, metadata: KeyMetadata) -> bool:
        """检查是否需要轮转"""
        if metadata.status != KeyStatus.ACTIVE:
            return False
        
        last_rotation = metadata.rotated_at or metadata.created_at
        return datetime.now() - last_rotation > self.rotation_interval
    
    def is_in_grace_period(self, metadata: KeyMetadata) -> bool:
        """检查是否在宽限期内"""
        if metadata.status != KeyStatus.PENDING_ROTATION:
            return False
        
        if metadata.rotated_at is None:
            return False
        
        return datetime.now() - metadata.rotated_at <= self.grace_period


class KeyManager:
    """密钥管理器"""
    
    def __init__(
        self,
        store: SecretStore = None,
        rotation_policy: KeyRotationPolicy = None
    ):
        self.store = store or FileSecretStore()
        self.rotation_policy = rotation_policy or KeyRotationPolicy()
        self._key_cache: Dict[str, Tuple[str, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    async def create_key(
        self,
        key_id: str,
        key_type: KeyType,
        purpose: str = "",
        expires_in_days: int = None,
        key_value: str = None
    ) -> KeyMetadata:
        """创建密钥"""
        # 生成密钥值
        if key_value is None:
            if key_type == KeyType.SYMMETRIC:
                key_value = base64.b64encode(os.urandom(32)).decode()
            elif key_type == KeyType.API_KEY:
                key_value = secrets.token_urlsafe(32)
            elif key_type == KeyType.JWT_SECRET:
                key_value = secrets.token_hex(32)
            else:
                key_value = secrets.token_urlsafe(48)
        
        # 创建元数据
        metadata = KeyMetadata(
            key_id=key_id,
            key_type=key_type,
            status=KeyStatus.ACTIVE,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None,
            algorithm="AES-256" if key_type == KeyType.SYMMETRIC else "HMAC-SHA256",
            purpose=purpose
        )
        
        # 存储
        await self.store.set_secret(key_id, key_value, metadata)
        
        logger.info("密钥已创建", key_id=key_id, key_type=key_type.value)
        return metadata
    
    async def get_key(self, key_id: str) -> Optional[str]:
        """获取密钥"""
        # 检查缓存
        if key_id in self._key_cache:
            value, cached_at = self._key_cache[key_id]
            if datetime.now() - cached_at < self._cache_ttl:
                return value
        
        # 从存储获取
        value = await self.store.get_secret(key_id)
        
        if value:
            self._key_cache[key_id] = (value, datetime.now())
        
        return value
    
    async def rotate_key(self, key_id: str) -> Optional[KeyMetadata]:
        """轮转密钥"""
        # 获取当前密钥元数据
        secrets_list = await self.store.list_secrets()
        current_metadata = None
        for meta in secrets_list:
            if meta.key_id == key_id:
                current_metadata = meta
                break
        
        if not current_metadata:
            logger.error("密钥不存在", key_id=key_id)
            return None
        
        # 创建新版本的密钥ID
        new_version = current_metadata.version + 1
        new_key_id = f"{key_id}_v{new_version}"
        
        # 生成新密钥
        if current_metadata.key_type == KeyType.SYMMETRIC:
            new_value = base64.b64encode(os.urandom(32)).decode()
        else:
            new_value = secrets.token_urlsafe(48)
        
        # 创建新元数据
        new_metadata = KeyMetadata(
            key_id=new_key_id,
            key_type=current_metadata.key_type,
            status=KeyStatus.ACTIVE,
            created_at=datetime.now(),
            expires_at=current_metadata.expires_at,
            version=new_version,
            algorithm=current_metadata.algorithm,
            purpose=current_metadata.purpose
        )
        
        # 存储新密钥
        await self.store.set_secret(new_key_id, new_value, new_metadata)
        
        # 更新旧密钥状态
        current_metadata.status = KeyStatus.PENDING_ROTATION
        current_metadata.rotated_at = datetime.now()
        await self.store.set_secret(
            key_id,
            await self.store.get_secret(key_id),
            current_metadata
        )
        
        # 清除缓存
        self._key_cache.pop(key_id, None)
        
        logger.info("密钥已轮转", old_key=key_id, new_key=new_key_id)
        return new_metadata
    
    async def revoke_key(self, key_id: str, reason: str = ""):
        """撤销密钥"""
        secrets_list = await self.store.list_secrets()
        for meta in secrets_list:
            if meta.key_id == key_id:
                meta.status = KeyStatus.COMPROMISED
                await self.store.set_secret(
                    key_id,
                    await self.store.get_secret(key_id),
                    meta
                )
                break
        
        self._key_cache.pop(key_id, None)
        
        logger.warning("密钥已撤销", key_id=key_id, reason=reason)
    
    async def check_and_rotate(self) -> List[str]:
        """检查并轮转需要轮转的密钥"""
        rotated = []
        
        secrets_list = await self.store.list_secrets()
        for meta in secrets_list:
            if self.rotation_policy.needs_rotation(meta):
                await self.rotate_key(meta.key_id)
                rotated.append(meta.key_id)
        
        return rotated
    
    async def get_active_key_for_purpose(self, purpose: str) -> Optional[Tuple[str, str]]:
        """获取指定用途的活动密钥"""
        secrets_list = await self.store.list_secrets()
        
        for meta in secrets_list:
            if meta.purpose == purpose and meta.status == KeyStatus.ACTIVE:
                value = await self.get_key(meta.key_id)
                if value:
                    return meta.key_id, value
        
        return None


class APIKeyManager:
    """API密钥管理器"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self._api_keys: Dict[str, Dict[str, Any]] = {}  # key_hash -> metadata
    
    async def create_api_key(
        self,
        name: str,
        owner_id: int,
        permissions: List[str] = None,
        expires_in_days: int = 365
    ) -> str:
        """创建API密钥"""
        key_id = f"api_{secrets.token_hex(8)}"
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        metadata = await self.key_manager.create_key(
            key_id=key_id,
            key_type=KeyType.API_KEY,
            purpose=f"API Key for {name}",
            expires_in_days=expires_in_days,
            key_value=api_key
        )
        
        self._api_keys[key_hash] = {
            "key_id": key_id,
            "name": name,
            "owner_id": owner_id,
            "permissions": permissions or ["read"],
            "created_at": datetime.now().isoformat(),
            "last_used": None
        }
        
        logger.info("API密钥已创建", name=name, owner_id=owner_id)
        
        # 返回完整密钥（只显示一次）
        return f"{key_id}.{api_key}"
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """验证API密钥"""
        try:
            key_id, key_value = api_key.split(".", 1)
        except ValueError:
            return None
        
        # 从存储获取
        stored_key = await self.key_manager.get_key(key_id)
        if not stored_key:
            return None
        
        # 验证
        if not secrets.compare_digest(stored_key, key_value):
            return None
        
        # 获取元数据
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        if key_hash in self._api_keys:
            info = self._api_keys[key_hash]
            info["last_used"] = datetime.now().isoformat()
            return info
        
        return {"key_id": key_id, "valid": True}
    
    async def revoke_api_key(self, key_id: str):
        """撤销API密钥"""
        await self.key_manager.revoke_key(key_id, "User requested revocation")


class JWTKeyManager:
    """JWT密钥管理器"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self._current_key_id: Optional[str] = None
    
    async def get_signing_key(self) -> Tuple[str, str]:
        """获取签名密钥"""
        result = await self.key_manager.get_active_key_for_purpose("jwt_signing")
        
        if result:
            return result
        
        # 创建新密钥
        metadata = await self.key_manager.create_key(
            key_id=f"jwt_signing_{int(time.time())}",
            key_type=KeyType.JWT_SECRET,
            purpose="jwt_signing",
            expires_in_days=90
        )
        
        key = await self.key_manager.get_key(metadata.key_id)
        self._current_key_id = metadata.key_id
        
        return metadata.key_id, key
    
    async def get_verification_keys(self) -> List[Tuple[str, str]]:
        """获取所有可用于验证的密钥（包括轮转中的旧密钥）"""
        keys = []
        secrets_list = await self.key_manager.store.list_secrets()
        
        for meta in secrets_list:
            if meta.purpose == "jwt_signing":
                if meta.status in [KeyStatus.ACTIVE, KeyStatus.PENDING_ROTATION]:
                    key = await self.key_manager.get_key(meta.key_id)
                    if key:
                        keys.append((meta.key_id, key))
        
        return keys
