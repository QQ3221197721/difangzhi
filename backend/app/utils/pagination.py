# 地方志数据智能管理系统 - 分页工具
"""分页参数处理、分页响应构建"""

from dataclasses import dataclass, field
from typing import Generic, List, Optional, TypeVar, Any
from math import ceil

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query

T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """获取限制数"""
        return self.page_size


@dataclass
class PaginatedResponse(Generic[T]):
    """分页响应"""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int = field(init=False)
    has_next: bool = field(init=False)
    has_prev: bool = field(init=False)
    
    def __post_init__(self):
        self.pages = ceil(self.total / self.page_size) if self.page_size > 0 else 0
        self.has_next = self.page < self.pages
        self.has_prev = self.page > 1
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": self.pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


def paginate(
    items: List[T],
    total: int,
    params: PaginationParams
) -> PaginatedResponse[T]:
    """
    创建分页响应
    
    Args:
        items: 数据列表
        total: 总数
        params: 分页参数
        
    Returns:
        分页响应对象
    """
    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def paginate_query(
    session: AsyncSession,
    query: Any,
    params: PaginationParams,
    scalar: bool = True
) -> PaginatedResponse:
    """
    分页查询（异步SQLAlchemy）
    
    Args:
        session: 数据库会话
        query: 查询对象
        params: 分页参数
        scalar: 是否返回标量结果
        
    Returns:
        分页响应
    """
    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据
    paginated_query = query.offset(params.offset).limit(params.limit)
    result = await session.execute(paginated_query)
    
    if scalar:
        items = list(result.scalars().all())
    else:
        items = list(result.all())
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


class CursorPagination(BaseModel):
    """游标分页参数"""
    cursor: Optional[str] = Field(default=None, description="游标")
    limit: int = Field(default=20, ge=1, le=100, description="每页数量")
    direction: str = Field(default="next", description="方向 (next/prev)")


@dataclass
class CursorPaginatedResponse(Generic[T]):
    """游标分页响应"""
    items: List[T]
    next_cursor: Optional[str]
    prev_cursor: Optional[str]
    has_more: bool
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "items": self.items,
            "next_cursor": self.next_cursor,
            "prev_cursor": self.prev_cursor,
            "has_more": self.has_more,
        }


def encode_cursor(value: Any) -> str:
    """
    编码游标
    
    Args:
        value: 游标值
        
    Returns:
        编码后的游标
    """
    import base64
    import json
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def decode_cursor(cursor: str) -> Any:
    """
    解码游标
    
    Args:
        cursor: 编码的游标
        
    Returns:
        解码后的值
    """
    import base64
    import json
    return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())


class PageInfo(BaseModel):
    """分页信息（用于API响应）"""
    total: int = Field(description="总数")
    page: int = Field(description="当前页")
    page_size: int = Field(description="每页数量")
    pages: int = Field(description="总页数")
    has_next: bool = Field(description="是否有下一页")
    has_prev: bool = Field(description="是否有上一页")
    
    @classmethod
    def from_paginated_response(cls, response: PaginatedResponse) -> "PageInfo":
        """从分页响应创建"""
        return cls(
            total=response.total,
            page=response.page,
            page_size=response.page_size,
            pages=response.pages,
            has_next=response.has_next,
            has_prev=response.has_prev,
        )
