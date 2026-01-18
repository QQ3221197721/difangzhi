"""
地方志数据智能管理系统 - API 路由汇总
"""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.categories import router as categories_router
from app.api.ai import router as ai_router
from app.api.analytics import router as analytics_router
from app.api.users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(categories_router)
api_router.include_router(ai_router)
api_router.include_router(analytics_router)
api_router.include_router(users_router)
