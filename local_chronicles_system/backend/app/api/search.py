"""
搜索API - 双模式搜索（AI智能搜索 + 筛选搜索）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from datetime import datetime
import uuid
import time
from typing import List, Optional

from app.core.database import get_db, get_redis
from app.core.security import get_current_verified_user
from app.models.models import User, ChronicleRecord, SearchHistory
from app.models.schemas import (
    AISearchRequest, FilterSearchRequest, FilterCondition,
    SearchResult, SearchResponse, APIResponse, CategoryTree, CategoryResponse
)
from app.services.ai_search import AISearchService


router = APIRouter(prefix="/search", tags=["搜索"])


@router.post("/ai", response_model=SearchResponse)
async def ai_search(
    request: AISearchRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """
    AI辅助智能搜索
    使用自然语言理解用户查询意图，返回相关数据
    """
    start_time = time.time()
    
    # 使用AI服务解析查询
    ai_service = AISearchService()
    parsed_query = await ai_service.parse_search_query(request.query)
    
    # 构建动态查询
    query = select(ChronicleRecord)
    conditions = []
    
    # 根据AI解析结果构建查询条件
    if parsed_query.get("region"):
        conditions.append(
            or_(
                ChronicleRecord.region.ilike(f"%{parsed_query['region']}%"),
                ChronicleRecord.region_city.ilike(f"%{parsed_query['region']}%"),
                ChronicleRecord.region_province.ilike(f"%{parsed_query['region']}%")
            )
        )
    
    if parsed_query.get("year"):
        conditions.append(ChronicleRecord.year == parsed_query["year"])
    
    if parsed_query.get("year_range"):
        year_range = parsed_query["year_range"]
        if year_range.get("start"):
            conditions.append(ChronicleRecord.year >= year_range["start"])
        if year_range.get("end"):
            conditions.append(ChronicleRecord.year <= year_range["end"])
    
    if parsed_query.get("work_category"):
        conditions.append(ChronicleRecord.work_category.ilike(f"%{parsed_query['work_category']}%"))
    
    if parsed_query.get("unit"):
        conditions.append(ChronicleRecord.unit.ilike(f"%{parsed_query['unit']}%"))
    
    if parsed_query.get("person"):
        conditions.append(ChronicleRecord.person.ilike(f"%{parsed_query['person']}%"))
    
    # 全文搜索
    if parsed_query.get("keywords"):
        keywords = parsed_query["keywords"]
        keyword_conditions = []
        for keyword in keywords:
            keyword_conditions.append(
                or_(
                    ChronicleRecord.title.ilike(f"%{keyword}%"),
                    ChronicleRecord.content.ilike(f"%{keyword}%"),
                    ChronicleRecord.summary.ilike(f"%{keyword}%")
                )
            )
        if keyword_conditions:
            conditions.append(or_(*keyword_conditions))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(ChronicleRecord.created_at.desc()).limit(request.limit)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # 计算执行时间
    execution_time = int((time.time() - start_time) * 1000)
    
    # 记录搜索历史
    search_history = SearchHistory(
        user_id=current_user.id,
        query_text=request.query,
        filters=parsed_query,
        search_type="ai_search",
        results_count=len(records),
        execution_time_ms=execution_time
    )
    db.add(search_history)
    await db.commit()
    
    return SearchResponse(
        results=[
            SearchResult(
                id=r.id,
                title=r.title,
                content=r.content[:500] if r.content else None,
                summary=r.summary,
                region=r.region,
                region_city=r.region_city,
                year=r.year,
                unit=r.unit,
                person=r.person,
                income=r.income,
                work_category=r.work_category,
                tags=r.tags or {},
                confidence_score=r.confidence_score,
                created_at=r.created_at
            )
            for r in records
        ],
        total=len(records),
        page=1,
        page_size=request.limit,
        search_type="ai_search",
        execution_time_ms=execution_time
    )


@router.post("/filter", response_model=SearchResponse)
async def filter_search(
    request: FilterSearchRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """
    标签筛选搜索
    用户选择分类标签进行精确筛选
    例如：选择"辽宁葫芦岛市"和"工业"，返回同时满足这两个条件的数据
    """
    start_time = time.time()
    filters = request.filters
    
    # 构建查询
    query = select(ChronicleRecord)
    count_query = select(func.count(ChronicleRecord.id))
    conditions = []
    
    # 地区筛选
    if filters.region:
        conditions.append(
            or_(
                ChronicleRecord.region.ilike(f"%{filters.region}%"),
                ChronicleRecord.region_city.ilike(f"%{filters.region}%"),
                ChronicleRecord.region_province.ilike(f"%{filters.region}%"),
                ChronicleRecord.region_district.ilike(f"%{filters.region}%")
            )
        )
    
    if filters.region_province:
        conditions.append(ChronicleRecord.region_province == filters.region_province)
    
    if filters.region_city:
        conditions.append(ChronicleRecord.region_city == filters.region_city)
    
    # 年份筛选
    if filters.year_start:
        conditions.append(ChronicleRecord.year >= filters.year_start)
    if filters.year_end:
        conditions.append(ChronicleRecord.year <= filters.year_end)
    
    # 单位筛选
    if filters.unit:
        conditions.append(ChronicleRecord.unit.ilike(f"%{filters.unit}%"))
    
    # 人物筛选
    if filters.person:
        conditions.append(ChronicleRecord.person.ilike(f"%{filters.person}%"))
    
    # 收入范围筛选
    if filters.income_min is not None:
        conditions.append(ChronicleRecord.income >= filters.income_min)
    if filters.income_max is not None:
        conditions.append(ChronicleRecord.income <= filters.income_max)
    
    # 工作类别筛选
    if filters.work_category:
        conditions.append(ChronicleRecord.work_category == filters.work_category)
    
    # 标签筛选（JSON字段）
    if filters.tags:
        for tag_key, tag_values in filters.tags.items():
            if tag_values:
                # PostgreSQL JSONB查询
                tag_conditions = []
                for value in tag_values:
                    tag_conditions.append(
                        ChronicleRecord.tags[tag_key].astext == value
                    )
                if tag_conditions:
                    conditions.append(or_(*tag_conditions))
    
    # 应用条件
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 排序
    if request.sort_by:
        sort_column = getattr(ChronicleRecord, request.sort_by, None)
        if sort_column:
            if request.sort_order == "asc":
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(ChronicleRecord.created_at.desc())
    
    # 分页
    offset = (request.page - 1) * request.page_size
    query = query.offset(offset).limit(request.page_size)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    execution_time = int((time.time() - start_time) * 1000)
    
    # 记录搜索历史
    search_history = SearchHistory(
        user_id=current_user.id,
        filters=filters.model_dump(),
        search_type="filter_search",
        results_count=total,
        execution_time_ms=execution_time
    )
    db.add(search_history)
    await db.commit()
    
    return SearchResponse(
        results=[
            SearchResult(
                id=r.id,
                title=r.title,
                content=r.content[:500] if r.content else None,
                summary=r.summary,
                region=r.region,
                region_city=r.region_city,
                year=r.year,
                unit=r.unit,
                person=r.person,
                income=r.income,
                work_category=r.work_category,
                tags=r.tags or {},
                confidence_score=r.confidence_score,
                created_at=r.created_at
            )
            for r in records
        ],
        total=total,
        page=request.page,
        page_size=request.page_size,
        search_type="filter_search",
        execution_time_ms=execution_time
    )


@router.get("/categories", response_model=APIResponse)
async def get_categories(
    db: AsyncSession = Depends(get_db)
):
    """获取所有分类标签（用于筛选界面）"""
    from app.core.config import CATEGORY_CONFIG
    
    # 获取动态分类的实际值
    dynamic_values = {}
    
    # 获取地区列表
    region_result = await db.execute(
        select(ChronicleRecord.region_province, ChronicleRecord.region_city)
        .distinct()
        .where(ChronicleRecord.region_city.isnot(None))
    )
    regions = region_result.all()
    
    region_tree = {}
    for province, city in regions:
        if province:
            if province not in region_tree:
                region_tree[province] = []
            if city and city not in region_tree[province]:
                region_tree[province].append(city)
    
    dynamic_values["地区"] = region_tree
    
    # 获取工作类别列表
    work_result = await db.execute(
        select(ChronicleRecord.work_category)
        .distinct()
        .where(ChronicleRecord.work_category.isnot(None))
    )
    work_categories = [r[0] for r in work_result.all()]
    dynamic_values["工作类别"] = work_categories
    
    # 获取年份范围
    year_result = await db.execute(
        select(func.min(ChronicleRecord.year), func.max(ChronicleRecord.year))
    )
    year_range = year_result.one()
    dynamic_values["年份"] = {
        "min": year_range[0] or 2000,
        "max": year_range[1] or 2050
    }
    
    # 获取单位列表
    unit_result = await db.execute(
        select(ChronicleRecord.unit)
        .distinct()
        .where(ChronicleRecord.unit.isnot(None))
        .limit(100)
    )
    units = [r[0] for r in unit_result.all()]
    dynamic_values["单位"] = units
    
    return APIResponse(
        success=True,
        message="获取分类成功",
        data={
            "config": CATEGORY_CONFIG,
            "values": dynamic_values
        }
    )


@router.get("/record/{record_id}", response_model=SearchResult)
async def get_record_detail(
    record_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """获取记录详情"""
    result = await db.execute(
        select(ChronicleRecord).where(ChronicleRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    return SearchResult(
        id=record.id,
        title=record.title,
        content=record.content,
        summary=record.summary,
        region=record.region,
        region_city=record.region_city,
        year=record.year,
        unit=record.unit,
        person=record.person,
        income=record.income,
        work_category=record.work_category,
        tags=record.tags or {},
        confidence_score=record.confidence_score,
        created_at=record.created_at
    )


@router.get("/suggestions")
async def get_search_suggestions(
    query: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """获取搜索建议"""
    suggestions = []
    
    # 从标题中获取建议
    title_result = await db.execute(
        select(ChronicleRecord.title)
        .where(ChronicleRecord.title.ilike(f"%{query}%"))
        .distinct()
        .limit(5)
    )
    suggestions.extend([r[0] for r in title_result.all()])
    
    # 从地区中获取建议
    region_result = await db.execute(
        select(ChronicleRecord.region_city)
        .where(ChronicleRecord.region_city.ilike(f"%{query}%"))
        .distinct()
        .limit(5)
    )
    suggestions.extend([r[0] for r in region_result.all() if r[0]])
    
    return {"suggestions": list(set(suggestions))[:10]}


@router.get("/history")
async def get_search_history(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20
):
    """获取搜索历史"""
    result = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    
    return {
        "history": [
            {
                "id": str(h.id),
                "query_text": h.query_text,
                "filters": h.filters,
                "search_type": h.search_type,
                "results_count": h.results_count,
                "created_at": h.created_at.isoformat()
            }
            for h in history
        ]
    }
