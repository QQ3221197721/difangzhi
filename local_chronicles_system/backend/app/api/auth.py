"""
认证API路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db, get_redis
from app.core.security import (
    get_password_hash, verify_password, create_access_token, 
    create_refresh_token, decode_token, get_current_user,
    get_current_active_user, validate_password_strength,
    validate_id_card, encrypt_sensitive_data, mask_id_card, mask_phone
)
from app.core.config import settings
from app.models.models import User, UserStatus, UserRole, UserLocation, AuditLog
from app.models.schemas import (
    UserRegister, UserLogin, RealNameVerification, 
    TokenResponse, UserResponse, UserProfile, LocationData, APIResponse
)


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=APIResponse)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 验证密码强度
    is_valid, msg = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    
    # 检查用户名是否存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱是否存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 创建用户
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        status=UserStatus.PENDING_VERIFICATION,
        role=UserRole.USER
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return APIResponse(
        success=True,
        message="注册成功，请完成实名认证",
        data={"user_id": str(new_user.id)}
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录（需要位置信息）"""
    # 查找用户
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        # 记录失败尝试
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.status = UserStatus.BANNED
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 检查账户状态
    if user.status == UserStatus.BANNED:
        raise HTTPException(status_code=403, detail="账户已被禁用")
    
    # 检查实名认证
    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="请先完成实名认证",
            headers={"X-Require-Verification": "true"}
        )
    
    # 强制获取位置信息
    if not login_data.location:
        raise HTTPException(
            status_code=400,
            detail="请授权位置信息访问",
            headers={"X-Require-Location": "true"}
        )
    
    # 记录位置
    location = UserLocation(
        user_id=user.id,
        latitude=login_data.location.get("latitude", 0),
        longitude=login_data.location.get("longitude", 0),
        accuracy=login_data.location.get("accuracy"),
        ip_address=request.client.host if request.client else None
    )
    db.add(location)
    
    # 更新登录信息
    user.failed_login_attempts = 0
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request.client else None
    
    # 记录审计日志
    audit_log = AuditLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        details={"location": login_data.location}
    )
    db.add(audit_log)
    
    await db.commit()
    
    # 生成令牌
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/verify-identity", response_model=APIResponse)
async def verify_identity(
    verification: RealNameVerification,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """实名认证"""
    # 验证身份证格式
    is_valid, msg = validate_id_card(verification.id_card)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    
    # 检查身份证是否已被使用
    id_card_hash = encrypt_sensitive_data(verification.id_card)
    result = await db.execute(
        select(User).where(User.id_card == id_card_hash).where(User.id != current_user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该身份证已被其他账户绑定")
    
    # TODO: 调用实名认证第三方API验证
    # response = await call_real_name_api(verification.real_name, verification.id_card)
    # if not response.success:
    #     raise HTTPException(status_code=400, detail="实名认证失败")
    
    # 更新用户信息
    current_user.real_name = verification.real_name
    current_user.id_card = id_card_hash
    current_user.phone = verification.phone
    current_user.is_verified = True
    current_user.verification_time = datetime.utcnow()
    current_user.status = UserStatus.ACTIVE
    
    await db.commit()
    
    return APIResponse(
        success=True,
        message="实名认证成功",
        data={"is_verified": True}
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """刷新令牌"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户信息"""
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        real_name_masked=mask_id_card(current_user.real_name) if current_user.real_name else None,
        phone_masked=mask_phone(current_user.phone) if current_user.phone else None,
        is_verified=current_user.is_verified,
        role=current_user.role.value,
        last_login_at=current_user.last_login_at
    )


@router.post("/logout", response_model=APIResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """登出"""
    # 记录审计日志
    audit_log = AuditLog(
        user_id=current_user.id,
        action="logout",
        resource_type="user",
        resource_id=str(current_user.id),
        ip_address=request.client.host if request.client else None
    )
    db.add(audit_log)
    await db.commit()
    
    # TODO: 将令牌加入黑名单（使用Redis）
    
    return APIResponse(success=True, message="登出成功")


@router.post("/record-location", response_model=APIResponse)
async def record_location(
    request: Request,
    location: LocationData,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """记录用户位置"""
    new_location = UserLocation(
        user_id=current_user.id,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy=location.accuracy,
        address=location.address,
        ip_address=request.client.host if request.client else None
    )
    
    db.add(new_location)
    await db.commit()
    
    return APIResponse(success=True, message="位置已记录")
