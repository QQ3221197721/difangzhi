"""
数据分析和可视化API
使用pandas进行数据分析，matplotlib进行可视化
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 非GUI后端
import seaborn as sns
import io
import base64
import json
from typing import List
import uuid

from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, ChronicleRecord
from app.models.schemas import (
    AnalysisRequest, VisualizationRequest, AnalysisResponse, 
    VisualizationResponse, APIResponse, AnalysisTypeEnum, VisualizationTypeEnum
)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

router = APIRouter(prefix="/analysis", tags=["数据分析"])


async def get_records_dataframe(
    record_ids: List[uuid.UUID],
    db: AsyncSession
) -> pd.DataFrame:
    """将记录转换为DataFrame"""
    result = await db.execute(
        select(ChronicleRecord).where(ChronicleRecord.id.in_(record_ids))
    )
    records = result.scalars().all()
    
    if not records:
        raise HTTPException(status_code=404, detail="未找到指定记录")
    
    data = []
    for r in records:
        data.append({
            'id': str(r.id),
            'title': r.title,
            'region': r.region,
            'region_province': r.region_province,
            'region_city': r.region_city,
            'year': r.year,
            'unit': r.unit,
            'person': r.person,
            'income': r.income,
            'work_category': r.work_category,
            **(r.numeric_data or {})
        })
    
    return pd.DataFrame(data)


@router.post("/summary", response_model=AnalysisResponse)
async def analyze_summary(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """数据汇总分析"""
    df = await get_records_dataframe(request.record_ids, db)
    
    summary = {
        "total_records": len(df),
        "columns": list(df.columns),
    }
    
    # 数值列统计
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        summary["numeric_stats"] = df[numeric_cols].describe().to_dict()
    
    # 分类统计
    if 'work_category' in df.columns:
        summary["work_category_distribution"] = df['work_category'].value_counts().to_dict()
    
    if 'region_city' in df.columns:
        summary["region_distribution"] = df['region_city'].value_counts().head(10).to_dict()
    
    if 'year' in df.columns:
        summary["year_distribution"] = df['year'].value_counts().sort_index().to_dict()
    
    # 收入统计
    if 'income' in df.columns and df['income'].notna().any():
        income_stats = {
            "mean": float(df['income'].mean()),
            "median": float(df['income'].median()),
            "min": float(df['income'].min()),
            "max": float(df['income'].max()),
            "sum": float(df['income'].sum())
        }
        summary["income_stats"] = income_stats
    
    return AnalysisResponse(
        analysis_type="summary",
        data=summary,
        summary=f"共分析 {len(df)} 条记录，包含 {len(numeric_cols)} 个数值字段"
    )


@router.post("/trend", response_model=AnalysisResponse)
async def analyze_trend(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """趋势分析"""
    df = await get_records_dataframe(request.record_ids, db)
    
    if 'year' not in df.columns or df['year'].isna().all():
        raise HTTPException(status_code=400, detail="数据中没有年份信息")
    
    group_field = request.group_by or 'work_category'
    metrics = request.metrics or ['income']
    
    trend_data = {}
    
    # 按年份分组
    year_group = df.groupby('year')
    trend_data["by_year"] = {}
    
    for metric in metrics:
        if metric in df.columns:
            trend_data["by_year"][metric] = year_group[metric].mean().to_dict()
    
    # 按分组字段和年份分组
    if group_field in df.columns:
        grouped = df.groupby([group_field, 'year'])
        trend_data["by_group"] = {}
        
        for metric in metrics:
            if metric in df.columns:
                pivot = df.pivot_table(
                    values=metric, 
                    index='year', 
                    columns=group_field, 
                    aggfunc='mean'
                )
                trend_data["by_group"][metric] = pivot.to_dict()
    
    return AnalysisResponse(
        analysis_type="trend",
        data=trend_data,
        summary=f"趋势分析完成，涵盖 {df['year'].nunique()} 个年份"
    )


@router.post("/comparison", response_model=AnalysisResponse)
async def analyze_comparison(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """对比分析"""
    df = await get_records_dataframe(request.record_ids, db)
    
    group_field = request.group_by or 'region_city'
    metrics = request.metrics or ['income']
    
    if group_field not in df.columns:
        raise HTTPException(status_code=400, detail=f"数据中没有 {group_field} 字段")
    
    comparison_data = {}
    grouped = df.groupby(group_field)
    
    for metric in metrics:
        if metric in df.columns and df[metric].dtype in ['int64', 'float64']:
            comparison_data[metric] = {
                "mean": grouped[metric].mean().to_dict(),
                "sum": grouped[metric].sum().to_dict(),
                "count": grouped[metric].count().to_dict(),
                "min": grouped[metric].min().to_dict(),
                "max": grouped[metric].max().to_dict()
            }
    
    return AnalysisResponse(
        analysis_type="comparison",
        data=comparison_data,
        summary=f"对比分析完成，按 {group_field} 分组，共 {df[group_field].nunique()} 个分组"
    )


@router.post("/distribution", response_model=AnalysisResponse)
async def analyze_distribution(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """分布分析"""
    df = await get_records_dataframe(request.record_ids, db)
    
    metrics = request.metrics or ['income']
    distribution_data = {}
    
    for metric in metrics:
        if metric in df.columns:
            if df[metric].dtype in ['int64', 'float64']:
                # 数值型分布
                distribution_data[metric] = {
                    "histogram": pd.cut(df[metric], bins=10).value_counts().sort_index().to_dict(),
                    "quartiles": df[metric].quantile([0.25, 0.5, 0.75]).to_dict(),
                    "skewness": float(df[metric].skew()),
                    "kurtosis": float(df[metric].kurtosis())
                }
            else:
                # 分类型分布
                distribution_data[metric] = {
                    "value_counts": df[metric].value_counts().to_dict(),
                    "unique_count": int(df[metric].nunique())
                }
    
    return AnalysisResponse(
        analysis_type="distribution",
        data=distribution_data,
        summary=f"分布分析完成，分析了 {len(metrics)} 个指标"
    )


@router.post("/correlation", response_model=AnalysisResponse)
async def analyze_correlation(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """相关性分析"""
    df = await get_records_dataframe(request.record_ids, db)
    
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    if len(numeric_cols) < 2:
        raise HTTPException(status_code=400, detail="需要至少两个数值字段进行相关性分析")
    
    correlation_matrix = df[numeric_cols].corr().to_dict()
    
    return AnalysisResponse(
        analysis_type="correlation",
        data={"correlation_matrix": correlation_matrix},
        summary=f"相关性分析完成，分析了 {len(numeric_cols)} 个数值字段"
    )


@router.post("/visualize", response_model=VisualizationResponse)
async def create_visualization(
    request: VisualizationRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """创建可视化图表"""
    df = await get_records_dataframe(request.record_ids, db)
    
    if request.x_field not in df.columns:
        raise HTTPException(status_code=400, detail=f"字段 {request.x_field} 不存在")
    if request.y_field not in df.columns:
        raise HTTPException(status_code=400, detail=f"字段 {request.y_field} 不存在")
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(12, 8))
    title = request.title or f"{request.y_field} by {request.x_field}"
    
    if request.chart_type == VisualizationTypeEnum.BAR:
        if request.group_field and request.group_field in df.columns:
            pivot = df.pivot_table(
                values=request.y_field, 
                index=request.x_field, 
                columns=request.group_field, 
                aggfunc='mean'
            )
            pivot.plot(kind='bar', ax=ax)
        else:
            grouped = df.groupby(request.x_field)[request.y_field].mean()
            grouped.plot(kind='bar', ax=ax, color='steelblue')
        ax.set_xlabel(request.x_field)
        ax.set_ylabel(request.y_field)
        
    elif request.chart_type == VisualizationTypeEnum.LINE:
        if request.group_field and request.group_field in df.columns:
            for name, group in df.groupby(request.group_field):
                group_sorted = group.sort_values(request.x_field)
                ax.plot(group_sorted[request.x_field], group_sorted[request.y_field], marker='o', label=name)
            ax.legend()
        else:
            df_sorted = df.sort_values(request.x_field)
            ax.plot(df_sorted[request.x_field], df_sorted[request.y_field], marker='o', color='steelblue')
        ax.set_xlabel(request.x_field)
        ax.set_ylabel(request.y_field)
        
    elif request.chart_type == VisualizationTypeEnum.PIE:
        value_counts = df[request.x_field].value_counts()
        ax.pie(value_counts.values, labels=value_counts.index, autopct='%1.1f%%')
        
    elif request.chart_type == VisualizationTypeEnum.SCATTER:
        if request.group_field and request.group_field in df.columns:
            for name, group in df.groupby(request.group_field):
                ax.scatter(group[request.x_field], group[request.y_field], label=name, alpha=0.6)
            ax.legend()
        else:
            ax.scatter(df[request.x_field], df[request.y_field], alpha=0.6, color='steelblue')
        ax.set_xlabel(request.x_field)
        ax.set_ylabel(request.y_field)
        
    elif request.chart_type == VisualizationTypeEnum.HEATMAP:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if len(numeric_cols) >= 2:
            corr = df[numeric_cols].corr()
            sns.heatmap(corr, annot=True, cmap='coolwarm', ax=ax, fmt='.2f')
        else:
            raise HTTPException(status_code=400, detail="热力图需要至少两个数值字段")
    
    ax.set_title(title)
    plt.tight_layout()
    
    # 转换为base64
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close(fig)
    
    return VisualizationResponse(
        chart_type=request.chart_type.value,
        image_base64=image_base64,
        title=title
    )


@router.post("/export/excel")
async def export_to_excel(
    record_ids: List[uuid.UUID],
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """导出数据为Excel"""
    df = await get_records_dataframe(record_ids, db)
    
    # 重命名列为中文
    column_mapping = {
        'title': '标题',
        'region': '地区',
        'region_province': '省份',
        'region_city': '城市',
        'year': '年份',
        'unit': '单位',
        'person': '人物',
        'income': '收入',
        'work_category': '工作类别'
    }
    df = df.rename(columns=column_mapping)
    
    # 生成Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='数据')
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=data_export.xlsx"}
    )


@router.post("/export/csv")
async def export_to_csv(
    record_ids: List[uuid.UUID],
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """导出数据为CSV"""
    df = await get_records_dataframe(record_ids, db)
    
    csv_content = df.to_csv(index=False, encoding='utf-8-sig')
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data_export.csv"}
    )


@router.get("/chart-types")
async def get_chart_types():
    """获取支持的图表类型"""
    return {
        "chart_types": [
            {"value": "bar", "label": "柱状图", "description": "适合对比不同类别的数据"},
            {"value": "line", "label": "折线图", "description": "适合展示趋势变化"},
            {"value": "pie", "label": "饼图", "description": "适合展示占比分布"},
            {"value": "scatter", "label": "散点图", "description": "适合展示两个变量的关系"},
            {"value": "heatmap", "label": "热力图", "description": "适合展示相关性矩阵"}
        ]
    }
