"""
地方志数据智能管理系统 - 用户管理 API
"""
from typing import List, Optional
from datetime import datetime
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import get_db
from app.models import User, UserRole, LoginLog
from app.schemas.schemas import UserResponse, UserUpdate, ResponseBase, PaginatedResponse
from app.api.auth import get_current_active_user, require_admin, get_password_hash

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/", response_model=List[UserResponse])
async def list_users(
    keyword: Optional[str] = Query(None),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表（管理员）"""
    query = select(User)
    
    if keyword:
        query = query.where(
            User.username.ilike(f"%{keyword}%") |
            User.real_name.ilike(f"%{keyword}%") |
            User.email.ilike(f"%{keyword}%")
        )
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [UserResponse.model_validate(user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户信息"""
    # 只能更新自己或管理员更新任何人
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="无权修改此用户")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role: UserRole,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """更新用户角色（管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.role = role
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.put("/{user_id}/status", response_model=ResponseBase)
async def update_user_status(
    user_id: int,
    is_active: bool,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """启用/禁用用户（管理员）"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_active = is_active
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    return ResponseBase(message=f"用户已{'启用' if is_active else '禁用'}")


@router.put("/{user_id}/verify", response_model=ResponseBase)
async def verify_user(
    user_id: int,
    is_verified: bool,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """实名认证审核（管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_verified = is_verified
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    return ResponseBase(message=f"用户实名认证{'通过' if is_verified else '拒绝'}")


@router.put("/{user_id}/password", response_model=ResponseBase)
async def reset_password(
    user_id: int,
    new_password: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """重置用户密码（管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.hashed_password = get_password_hash(new_password)
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    return ResponseBase(message="密码已重置")


@router.get("/{user_id}/login-logs")
async def get_user_login_logs(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取用户登录日志"""
    result = await db.execute(
        select(LoginLog)
        .where(LoginLog.user_id == user_id)
        .order_by(LoginLog.login_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "ip_address": log.ip_address,
            "location": log.location,
            "user_agent": log.user_agent,
            "login_time": log.login_time.isoformat(),
            "is_success": log.is_success,
            "fail_reason": log.fail_reason
        }
        for log in logs
    ]


@router.delete("/{user_id}", response_model=ResponseBase)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """删除用户（软删除）"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.is_active = False
    user.updated_at = datetime.utcnow()
    await db.commit()
    
    return ResponseBase(message="用户已删除")


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """上传用户头像"""
    # 检查文件类型
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="不支持的图片格式，请上传 JPG/PNG/GIF/WEBP")
    
    # 检查文件大小 (5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")
    
    # 生成文件名
    ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
    filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    
    # 保存文件
    avatar_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    file_path = os.path.join(avatar_dir, filename)
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # 更新用户头像 URL
    avatar_url = f"/uploads/avatars/{filename}"
    current_user.avatar_url = avatar_url
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"avatar_url": avatar_url, "message": "头像上传成功"}
