#!/usr/bin/env python3
# 地方志数据智能管理系统 - 数据库初始化脚本
"""初始化数据库和默认数据"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine, Base, AsyncSession
from app.core.security import hash_password
from app.models.models import User, Category, UserRole


# 默认分类数据
DEFAULT_CATEGORIES = [
    # 地区分类
    {"name": "华东地区", "code": "region_east", "category_type": "region", "level": 1},
    {"name": "华北地区", "code": "region_north", "category_type": "region", "level": 1},
    {"name": "华南地区", "code": "region_south", "category_type": "region", "level": 1},
    {"name": "西南地区", "code": "region_southwest", "category_type": "region", "level": 1},
    {"name": "西北地区", "code": "region_northwest", "category_type": "region", "level": 1},
    {"name": "东北地区", "code": "region_northeast", "category_type": "region", "level": 1},
    
    # 年代分类
    {"name": "明清时期", "code": "era_mingqing", "category_type": "year", "level": 1},
    {"name": "民国时期", "code": "era_minguo", "category_type": "year", "level": 1},
    {"name": "建国初期", "code": "era_early_prc", "category_type": "year", "level": 1},
    {"name": "改革开放后", "code": "era_reform", "category_type": "year", "level": 1},
    {"name": "新时代", "code": "era_new", "category_type": "year", "level": 1},
    
    # 类型分类
    {"name": "政治制度", "code": "type_politics", "category_type": "other", "level": 1},
    {"name": "经济发展", "code": "type_economy", "category_type": "other", "level": 1},
    {"name": "文化教育", "code": "type_culture", "category_type": "other", "level": 1},
    {"name": "社会民生", "code": "type_society", "category_type": "other", "level": 1},
    {"name": "自然地理", "code": "type_geography", "category_type": "other", "level": 1},
    {"name": "人物传记", "code": "type_biography", "category_type": "other", "level": 1},
]


async def create_tables():
    """创建数据库表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ 数据库表创建完成")


async def create_default_admin():
    """创建默认管理员账户"""
    async with AsyncSession(engine) as session:
        # 检查是否已存在管理员
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("✓ 管理员账户已存在")
            return
        
        admin = User(
            username="admin",
            email="admin@localchronicles.com",
            hashed_password=hash_password("Admin@123456"),
            real_name="系统管理员",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True
        )
        session.add(admin)
        await session.commit()
        print("✓ 默认管理员账户创建完成 (admin / Admin@123456)")


async def create_default_categories():
    """创建默认分类"""
    async with AsyncSession(engine) as session:
        from sqlalchemy import select
        result = await session.execute(select(Category).limit(1))
        existing = result.scalar_one_or_none()
        
        if existing:
            print("✓ 默认分类已存在")
            return
        
        for cat_data in DEFAULT_CATEGORIES:
            category = Category(**cat_data)
            session.add(category)
        
        await session.commit()
        print(f"✓ 创建了 {len(DEFAULT_CATEGORIES)} 个默认分类")


async def main():
    """主函数"""
    print("开始初始化数据库...")
    print("-" * 40)
    
    try:
        await create_tables()
        await create_default_admin()
        await create_default_categories()
        
        print("-" * 40)
        print("✓ 数据库初始化完成！")
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
