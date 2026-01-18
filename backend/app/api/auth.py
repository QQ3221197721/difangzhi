"""
地方志数据智能管理系统 - 认证 API
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.database import get_db
from app.models import User, LoginLog, UserRole
from app.schemas.schemas import (
    UserCreate, UserResponse, UserLogin, TokenResponse,
    LocationUpdate, ResponseBase
)

router = APIRouter(prefix="/auth", tags=["认证"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


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
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


@router.post("/register", response_model=ResponseBase)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 检查用户名是否存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱是否存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 创建用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        real_name=user_data.real_name,
        id_card=user_data.id_card,
        phone=user_data.phone,
        role=UserRole.VIEWER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return ResponseBase(message="注册成功", data={"user_id": user.id})


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    # 查找用户
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()
    
    # 记录登录日志
    log = LoginLog(
        user_id=user.id if user else 0,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
        location=login_data.location,
        latitude=login_data.location.get("latitude") if login_data.location else None,
        longitude=login_data.location.get("longitude") if login_data.location else None,
    )
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        log.is_success = False
        log.fail_reason = "用户名或密码错误"
        if user:
            log.user_id = user.id
            db.add(log)
            await db.commit()
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if not user.is_active:
        log.is_success = False
        log.fail_reason = "用户已被禁用"
        db.add(log)
        await db.commit()
        raise HTTPException(status_code=401, detail="用户已被禁用")
    
    # 检查位置信息（如果要求）
    if settings.REQUIRE_LOCATION and not login_data.location:
        log.is_success = False
        log.fail_reason = "需要位置信息"
        db.add(log)
        await db.commit()
        raise HTTPException(status_code=400, detail="需要提供位置信息")
    
    # 更新用户登录信息
    user.last_login = datetime.utcnow()
    user.last_location = login_data.location
    
    # 记录成功登录
    db.add(log)
    await db.commit()
    
    # 生成令牌
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """刷新令牌"""
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="无效的刷新令牌")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    
    access_token = create_access_token(data={"sub": user.id})
    new_refresh_token = create_refresh_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return UserResponse.model_validate(current_user)


@router.put("/location", response_model=ResponseBase)
async def update_location(
    location: LocationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户位置"""
    current_user.last_location = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "address": location.address,
        "updated_at": datetime.utcnow().isoformat()
    }
    await db.commit()
    return ResponseBase(message="位置更新成功")


@router.post("/logout", response_model=ResponseBase)
async def logout(current_user: User = Depends(get_current_active_user)):
    """用户登出"""
    # 可以在这里添加令牌黑名单逻辑
    return ResponseBase(message="登出成功")


@router.post("/change-password", response_model=ResponseBase)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    
    # 检查新密码强度
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="密码至少8位")
    
    # 更新密码
    current_user.hashed_password = get_password_hash(new_password)
    await db.commit()
    
    return ResponseBase(message="密码修改成功")


@router.get("/login-logs")
async def get_login_logs(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20
):
    """获取当前用户的登录日志"""
    from sqlalchemy import desc
    
    offset = (page - 1) * page_size
    
    result = await db.execute(
        select(LoginLog)
        .where(LoginLog.user_id == current_user.id)
        .order_by(desc(LoginLog.login_time))
        .offset(offset)
        .limit(page_size)
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "login_time": log.login_time.isoformat() if log.login_time else None,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "latitude": log.latitude,
            "longitude": log.longitude,
            "success": log.is_success if hasattr(log, 'is_success') else True,
        }
        for log in logs
    ]
