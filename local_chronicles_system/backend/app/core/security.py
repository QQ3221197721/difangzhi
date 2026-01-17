"""
安全模块 - JWT认证、密码处理、权限控制
"""
from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import hashlib
import re

from app.core.config import settings
from app.core.database import get_db
from app.models.models import User, UserStatus, UserRole


# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码长度至少8位"
    if not re.search(r"[A-Z]", password):
        return False, "密码必须包含大写字母"
    if not re.search(r"[a-z]", password):
        return False, "密码必须包含小写字母"
    if not re.search(r"\d", password):
        return False, "密码必须包含数字"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "密码必须包含特殊字符"
    return True, "密码强度符合要求"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    token_type: str = payload.get("type")
    
    if user_id is None or token_type != "access":
        raise credentials_exception
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户未激活或已被禁用"
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """获取当前已实名认证用户"""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先完成实名认证"
        )
    return current_user


def require_role(allowed_roles: list[UserRole]):
    """角色权限装饰器"""
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user
    return role_checker


class RateLimiter:
    """速率限制器"""
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._cache = {}
    
    async def check(self, key: str) -> bool:
        """检查是否超过速率限制"""
        now = datetime.utcnow()
        minute_key = f"{key}:{now.strftime('%Y%m%d%H%M')}"
        
        if minute_key not in self._cache:
            self._cache[minute_key] = 0
        
        self._cache[minute_key] += 1
        
        # 清理旧数据
        old_keys = [k for k in self._cache if k < f"{key}:{(now - timedelta(minutes=2)).strftime('%Y%m%d%H%M')}"]
        for k in old_keys:
            del self._cache[k]
        
        return self._cache[minute_key] <= self.requests_per_minute


def encrypt_sensitive_data(data: str) -> str:
    """加密敏感数据（如身份证号）"""
    # 使用SHA-256哈希 + 加盐
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256(f"{salt}{data}".encode()).hexdigest()


def mask_id_card(id_card: str) -> str:
    """身份证号脱敏"""
    if len(id_card) == 18:
        return f"{id_card[:6]}********{id_card[-4:]}"
    return "****"


def mask_phone(phone: str) -> str:
    """手机号脱敏"""
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[-4:]}"
    return "****"


def validate_id_card(id_card: str) -> tuple[bool, str]:
    """验证身份证号格式"""
    if len(id_card) != 18:
        return False, "身份证号必须为18位"
    
    # 检查前17位是否为数字
    if not id_card[:17].isdigit():
        return False, "身份证号格式错误"
    
    # 检查最后一位
    if not (id_card[-1].isdigit() or id_card[-1].upper() == 'X'):
        return False, "身份证号格式错误"
    
    # 校验码验证
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    
    total = sum(int(id_card[i]) * weights[i] for i in range(17))
    expected_check = check_codes[total % 11]
    
    if id_card[-1].upper() != expected_check:
        return False, "身份证号校验失败"
    
    return True, "验证通过"
