# 地方志数据智能管理系统 - 加密工具
"""Token生成、哈希计算、加密解密等工具"""

import base64
import hashlib
import hmac
import secrets
import string
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# 默认密钥（生产环境应从配置读取）
_default_key: Optional[bytes] = None


def _get_fernet_key(key: Optional[str] = None) -> bytes:
    """获取Fernet加密密钥"""
    global _default_key
    
    if key:
        # 从密码派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'local_chronicles_salt',
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(key.encode()))
    
    if _default_key is None:
        _default_key = Fernet.generate_key()
    
    return _default_key


def generate_token(length: int = 32) -> str:
    """
    生成安全随机Token
    
    Args:
        length: Token长度
        
    Returns:
        Token字符串
    """
    return secrets.token_urlsafe(length)


def generate_random_string(
    length: int = 16,
    include_digits: bool = True,
    include_special: bool = False
) -> str:
    """
    生成随机字符串
    
    Args:
        length: 长度
        include_digits: 是否包含数字
        include_special: 是否包含特殊字符
        
    Returns:
        随机字符串
    """
    chars = string.ascii_letters
    
    if include_digits:
        chars += string.digits
    
    if include_special:
        chars += string.punctuation
    
    return ''.join(secrets.choice(chars) for _ in range(length))


def hash_string(
    text: str,
    algorithm: str = "sha256",
    salt: Optional[str] = None
) -> str:
    """
    计算字符串哈希
    
    Args:
        text: 原始文本
        algorithm: 哈希算法
        salt: 盐值
        
    Returns:
        哈希值
    """
    if salt:
        text = salt + text
    
    hash_func = getattr(hashlib, algorithm)
    return hash_func(text.encode()).hexdigest()


def verify_hash(
    text: str,
    hash_value: str,
    algorithm: str = "sha256",
    salt: Optional[str] = None
) -> bool:
    """
    验证哈希值
    
    Args:
        text: 原始文本
        hash_value: 期望的哈希值
        algorithm: 哈希算法
        salt: 盐值
        
    Returns:
        是否匹配
    """
    computed_hash = hash_string(text, algorithm, salt)
    return hmac.compare_digest(computed_hash, hash_value)


def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """
    加密数据
    
    Args:
        data: 原始数据
        key: 加密密钥
        
    Returns:
        加密后的数据（Base64编码）
    """
    fernet_key = _get_fernet_key(key)
    f = Fernet(fernet_key)
    encrypted = f.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(encrypted_data: str, key: Optional[str] = None) -> str:
    """
    解密数据
    
    Args:
        encrypted_data: 加密数据（Base64编码）
        key: 解密密钥
        
    Returns:
        解密后的数据
    """
    fernet_key = _get_fernet_key(key)
    f = Fernet(fernet_key)
    data = base64.urlsafe_b64decode(encrypted_data.encode())
    return f.decrypt(data).decode()


def generate_api_key() -> Tuple[str, str]:
    """
    生成API密钥对
    
    Returns:
        (key_id, key_secret)
    """
    key_id = f"ak_{secrets.token_hex(8)}"
    key_secret = secrets.token_urlsafe(32)
    return key_id, key_secret


def mask_string(
    text: str,
    visible_start: int = 3,
    visible_end: int = 4,
    mask_char: str = "*"
) -> str:
    """
    部分遮盖字符串
    
    Args:
        text: 原始字符串
        visible_start: 开头可见字符数
        visible_end: 结尾可见字符数
        mask_char: 遮盖字符
        
    Returns:
        遮盖后的字符串
    """
    if not text:
        return ""
    
    length = len(text)
    
    if length <= visible_start + visible_end:
        return mask_char * length
    
    mask_length = length - visible_start - visible_end
    return text[:visible_start] + mask_char * mask_length + text[-visible_end:]


def generate_verification_code(length: int = 6) -> str:
    """
    生成数字验证码
    
    Args:
        length: 验证码长度
        
    Returns:
        验证码
    """
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def compute_checksum(data: bytes) -> str:
    """
    计算数据校验和
    
    Args:
        data: 字节数据
        
    Returns:
        校验和（CRC32）
    """
    import zlib
    return format(zlib.crc32(data) & 0xffffffff, '08x')


def generate_signature(
    data: str,
    secret: str,
    algorithm: str = "sha256"
) -> str:
    """
    生成HMAC签名
    
    Args:
        data: 待签名数据
        secret: 密钥
        algorithm: 算法
        
    Returns:
        签名
    """
    hash_func = getattr(hashlib, algorithm)
    signature = hmac.new(
        secret.encode(),
        data.encode(),
        hash_func
    ).hexdigest()
    return signature


def verify_signature(
    data: str,
    signature: str,
    secret: str,
    algorithm: str = "sha256"
) -> bool:
    """
    验证HMAC签名
    
    Args:
        data: 原始数据
        signature: 签名
        secret: 密钥
        algorithm: 算法
        
    Returns:
        是否有效
    """
    expected = generate_signature(data, secret, algorithm)
    return hmac.compare_digest(expected, signature)
