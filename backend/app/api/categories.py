"""
地方志数据智能管理系统 - 分类管理 API
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models import User, Category
from app.schemas.schemas import (
    CategoryCreate, CategoryUpdate, CategoryResponse, ResponseBase
)
from app.api.auth import get_current_active_user, require_admin

router = APIRouter(prefix="/categories", tags=["分类管理"])


@router.get("/", response_model=List[CategoryResponse])
async def list_categories(
    category_type: Optional[str] = Query(None, description="分类类型"),
    level: Optional[int] = Query(None, description="层级"),
    parent_id: Optional[int] = Query(None, description="父分类ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取分类列表"""
    query = select(Category).where(Category.is_active == True)
    
    if category_type:
        query = query.where(Category.category_type == category_type)
    if level:
        query = query.where(Category.level == level)
    if parent_id:
        query = query.where(Category.parent_id == parent_id)
    else:
        # 默认获取顶级分类
        if not level:
            query = query.where(Category.parent_id == None)
    
    query = query.order_by(Category.sort_order, Category.id)
    
    result = await db.execute(query)
    categories = result.scalars().all()
    
    return [CategoryResponse.model_validate(cat) for cat in categories]


@router.get("/tree", response_model=List[CategoryResponse])
async def get_category_tree(
    category_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取分类树"""
    query = select(Category).where(
        Category.is_active == True,
        Category.parent_id == None
    ).options(selectinload(Category.children))
    
    if category_type:
        query = query.where(Category.category_type == category_type)
    
    query = query.order_by(Category.sort_order)
    
    result = await db.execute(query)
    categories = result.scalars().all()
    
    return [CategoryResponse.model_validate(cat) for cat in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取分类详情"""
    result = await db.execute(
        select(Category).where(Category.id == category_id).options(selectinload(Category.children))
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    return CategoryResponse.model_validate(category)


@router.post("/", response_model=CategoryResponse)
async def create_category(
    cat_data: CategoryCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """创建分类"""
    # 检查 code 是否唯一
    result = await db.execute(select(Category).where(Category.code == cat_data.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="分类代码已存在")
    
    # 确定层级
    level = 1
    if cat_data.parent_id:
        result = await db.execute(select(Category).where(Category.id == cat_data.parent_id))
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=400, detail="父分类不存在")
        level = parent.level + 1
    
    category = Category(
        name=cat_data.name,
        code=cat_data.code,
        category_type=cat_data.category_type,
        level=level,
        parent_id=cat_data.parent_id,
        description=cat_data.description,
        sort_order=cat_data.sort_order,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    
    return CategoryResponse.model_validate(category)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    cat_data: CategoryUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """更新分类"""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    update_data = cat_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)
    
    await db.commit()
    await db.refresh(category)
    
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}", response_model=ResponseBase)
async def delete_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """删除分类（软删除）"""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    # 软删除
    category.is_active = False
    await db.commit()
    
    return ResponseBase(message="分类已删除")


@router.get("/types/list", response_model=List[str])
async def get_category_types(db: AsyncSession = Depends(get_db)):
    """获取所有分类类型"""
    result = await db.execute(
        select(Category.category_type).distinct()
    )
    types = result.scalars().all()
    return types
