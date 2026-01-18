"""
地方志数据智能管理系统 - 数据分析 API
"""
import io
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from app.core.database import get_db
from app.models import User, Document, Category, DataStatus
from app.schemas.schemas import AnalyticsQuery, AnalyticsResult, ResponseBase
from app.api.auth import get_current_active_user, require_admin

router = APIRouter(prefix="/analytics", tags=["数据分析"])

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


@router.get("/overview")
async def get_overview(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取数据概览"""
    # 文档统计
    total_docs = await db.scalar(select(func.count()).select_from(Document))
    pending_docs = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == DataStatus.PENDING)
    )
    approved_docs = await db.scalar(
        select(func.count()).select_from(Document).where(Document.status == DataStatus.APPROVED)
    )
    
    # 用户统计
    total_users = await db.scalar(select(func.count()).select_from(User))
    active_users = await db.scalar(
        select(func.count()).select_from(User).where(User.is_active == True)
    )
    
    # 分类统计
    total_categories = await db.scalar(select(func.count()).select_from(Category))
    
    # 最近7天上传趋势
    week_ago = datetime.utcnow() - timedelta(days=7)
    daily_uploads = await db.execute(
        select(
            func.date(Document.created_at).label('date'),
            func.count().label('count')
        )
        .where(Document.created_at >= week_ago)
        .group_by(func.date(Document.created_at))
        .order_by(func.date(Document.created_at))
    )
    upload_trend = [{"date": str(row.date), "count": row.count} for row in daily_uploads]
    
    return {
        "documents": {
            "total": total_docs,
            "pending": pending_docs,
            "approved": approved_docs
        },
        "users": {
            "total": total_users,
            "active": active_users
        },
        "categories": total_categories,
        "upload_trend": upload_trend
    }


@router.get("/documents/by-region")
async def get_documents_by_region(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """按地区统计文档"""
    result = await db.execute(
        select(
            Document.region,
            func.count().label('count')
        )
        .where(Document.region != None)
        .group_by(Document.region)
        .order_by(func.count().desc())
    )
    data = [{"region": row.region or "未知", "count": row.count} for row in result]
    
    return AnalyticsResult(
        metric="documents_by_region",
        data=data,
        chart_type="bar",
        summary={"total_regions": len(data)}
    )


@router.get("/documents/by-year")
async def get_documents_by_year(
    year_start: Optional[int] = Query(None),
    year_end: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """按年份统计文档"""
    query = select(
        Document.year,
        func.count().label('count')
    ).where(Document.year != None)
    
    if year_start:
        query = query.where(Document.year >= year_start)
    if year_end:
        query = query.where(Document.year <= year_end)
    
    query = query.group_by(Document.year).order_by(Document.year)
    
    result = await db.execute(query)
    data = [{"year": row.year, "count": row.count} for row in result]
    
    return AnalyticsResult(
        metric="documents_by_year",
        data=data,
        chart_type="line",
        summary={"total_years": len(data)}
    )


@router.get("/documents/by-category")
async def get_documents_by_category(
    category_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """按分类统计文档"""
    from app.models import DocumentCategory
    
    query = select(
        Category.name,
        func.count(DocumentCategory.document_id).label('count')
    ).join(
        DocumentCategory, Category.id == DocumentCategory.category_id
    )
    
    if category_type:
        query = query.where(Category.category_type == category_type)
    
    query = query.group_by(Category.id, Category.name).order_by(func.count().desc())
    
    result = await db.execute(query)
    data = [{"category": row.name, "count": row.count} for row in result]
    
    return AnalyticsResult(
        metric="documents_by_category",
        data=data,
        chart_type="pie",
        summary={"total_categories": len(data)}
    )


@router.get("/documents/upload-trend")
async def get_upload_trend(
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取上传趋势"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            func.date(Document.created_at).label('date'),
            func.count().label('count')
        )
        .where(Document.created_at >= start_date)
        .group_by(func.date(Document.created_at))
        .order_by(func.date(Document.created_at))
    )
    data = [{"date": str(row.date), "count": row.count} for row in result]
    
    return AnalyticsResult(
        metric="upload_trend",
        data=data,
        chart_type="area",
        summary={"days": days, "total_uploads": sum(d["count"] for d in data)}
    )


@router.get("/chart/region-distribution")
async def get_region_chart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """生成地区分布图表"""
    result = await db.execute(
        select(
            Document.region,
            func.count().label('count')
        )
        .where(Document.region != None)
        .group_by(Document.region)
        .order_by(func.count().desc())
        .limit(10)
    )
    data = [(row.region or "未知", row.count) for row in result]
    
    if not data:
        data = [("暂无数据", 1)]
    
    # 生成图表
    fig, ax = plt.subplots(figsize=(12, 6))
    regions, counts = zip(*data)
    
    colors = sns.color_palette("husl", len(regions))
    bars = ax.barh(regions, counts, color=colors)
    
    ax.set_xlabel('文档数量')
    ax.set_title('文档地区分布 Top 10')
    ax.invert_yaxis()
    
    # 添加数值标签
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                str(count), va='center')
    
    plt.tight_layout()
    
    # 转为图片
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return StreamingResponse(buf, media_type="image/png")


@router.get("/chart/year-trend")
async def get_year_chart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """生成年份趋势图表"""
    result = await db.execute(
        select(
            Document.year,
            func.count().label('count')
        )
        .where(Document.year != None)
        .group_by(Document.year)
        .order_by(Document.year)
    )
    data = [(row.year, row.count) for row in result]
    
    if not data:
        data = [(2024, 0)]
    
    # 生成图表
    fig, ax = plt.subplots(figsize=(12, 6))
    years, counts = zip(*data)
    
    ax.plot(years, counts, marker='o', linewidth=2, markersize=8, color='#1890ff')
    ax.fill_between(years, counts, alpha=0.3, color='#1890ff')
    
    ax.set_xlabel('年份')
    ax.set_ylabel('文档数量')
    ax.set_title('文档年份分布趋势')
    ax.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return StreamingResponse(buf, media_type="image/png")


@router.get("/chart/category-pie")
async def get_category_pie_chart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """生成分类饼图"""
    from app.models import DocumentCategory
    
    result = await db.execute(
        select(
            Category.name,
            func.count(DocumentCategory.document_id).label('count')
        )
        .join(DocumentCategory, Category.id == DocumentCategory.category_id)
        .group_by(Category.id, Category.name)
        .order_by(func.count().desc())
        .limit(8)
    )
    data = [(row.name, row.count) for row in result]
    
    if not data:
        data = [("暂无数据", 1)]
    
    # 生成饼图
    fig, ax = plt.subplots(figsize=(10, 10))
    labels, sizes = zip(*data)
    
    colors = sns.color_palette("husl", len(labels))
    explode = [0.05] * len(labels)
    
    wedges, texts, autotexts = ax.pie(
        sizes, explode=explode, labels=labels, colors=colors,
        autopct='%1.1f%%', startangle=90, pctdistance=0.85
    )
    
    ax.set_title('文档分类分布')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return StreamingResponse(buf, media_type="image/png")


@router.post("/export")
async def export_analytics(
    query: AnalyticsQuery,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """导出分析数据为 Excel"""
    # 根据查询类型获取数据
    data = []
    
    if query.metric == "documents":
        result = await db.execute(
            select(Document).order_by(Document.created_at.desc()).limit(1000)
        )
        documents = result.scalars().all()
        data = [
            {
                "ID": doc.id,
                "标题": doc.title,
                "地区": doc.region,
                "年份": doc.year,
                "状态": doc.status.value,
                "创建时间": doc.created_at.isoformat()
            }
            for doc in documents
        ]
    
    # 转为 Excel
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=analytics_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )
