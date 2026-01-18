"""
地方志数据智能管理系统 - 文档 API
"""
import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import User, Document, Category, DocumentCategory, DataStatus
from app.schemas.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentListResponse,
    DocumentReview, SearchQuery, SearchResult, FileUploadResponse,
    ResponseBase, PaginatedResponse
)
from app.api.auth import get_current_active_user, require_admin
from app.services.storage_service import storage_service
from app.tasks.ai_tasks import process_document_task

router = APIRouter(prefix="/documents", tags=["文档管理"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    category_ids: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文档文件（AI 自动提取）"""
    # 检查文件类型
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}")
    
    # 检查文件大小
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过限制")
    
    # 生成文件路径
    file_id = str(uuid.uuid4())
    file_path = f"documents/{datetime.now().strftime('%Y/%m')}/{file_id}{file_ext}"
    
    # 上传到存储
    await storage_service.upload_file(file_path, content, file.content_type)
    
    # 解析标签和分类
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    cat_ids = [int(c) for c in category_ids.split(",")] if category_ids else []
    
    # 创建文档记录
    document = Document(
        title=title or file.filename,
        file_path=file_path,
        file_name=file.filename,
        file_size=len(content),
        file_type=file_ext,
        region=region,
        year=year,
        tags=tag_list,
        status=DataStatus.PENDING,
        upload_type="file",
        uploader_id=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # 添加分类关联
    for cat_id in cat_ids:
        db.add(DocumentCategory(document_id=document.id, category_id=cat_id))
    await db.commit()
    
    # 触发 AI 处理任务
    task = process_document_task.delay(document.id)
    
    return FileUploadResponse(
        file_id=file_id,
        file_name=file.filename,
        file_size=len(content),
        file_type=file_ext,
        task_id=task.id
    )


@router.post("/manual", response_model=DocumentResponse)
async def create_document_manual(
    doc_data: DocumentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """手动创建文档记录"""
    document = Document(
        title=doc_data.title,
        content=doc_data.content,
        source=doc_data.source,
        author=doc_data.author,
        region=doc_data.region,
        year=doc_data.year,
        tags=doc_data.tags,
        publish_date=doc_data.publish_date,
        status=DataStatus.PENDING,
        upload_type="manual",
        uploader_id=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # 添加分类关联
    for cat_id in doc_data.category_ids:
        db.add(DocumentCategory(document_id=document.id, category_id=cat_id))
    await db.commit()
    
    # 触发 AI 处理（生成摘要和关键词）
    process_document_task.delay(document.id)
    
    return DocumentResponse.model_validate(document)


@router.get("/", response_model=SearchResult)
async def list_documents(
    keyword: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    year_start: Optional[int] = Query(None),
    year_end: Optional[int] = Query(None),
    status: Optional[DataStatus] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文档列表"""
    query = select(Document)
    
    # 应用过滤条件
    conditions = []
    if keyword:
        conditions.append(
            or_(
                Document.title.ilike(f"%{keyword}%"),
                Document.content.ilike(f"%{keyword}%"),
                Document.tags.any(keyword)
            )
        )
    if region:
        conditions.append(Document.region == region)
    if year_start:
        conditions.append(Document.year >= year_start)
    if year_end:
        conditions.append(Document.year <= year_end)
    if status:
        conditions.append(Document.status == status)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()
    
    # 排序
    order_column = getattr(Document, sort_by, Document.created_at)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    # 分页
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return SearchResult(
        documents=[DocumentListResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文档详情"""
    query = select(Document).where(Document.id == document_id).options(
        selectinload(Document.categories).selectinload(DocumentCategory.category)
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 增加浏览次数
    document.view_count += 1
    await db.commit()
    
    return DocumentResponse.model_validate(document)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    doc_data: DocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """更新文档"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 检查权限
    if document.uploader_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.EDITOR]:
        raise HTTPException(status_code=403, detail="无权编辑此文档")
    
    # 更新字段
    update_data = doc_data.model_dump(exclude_unset=True)
    category_ids = update_data.pop("category_ids", None)
    
    for key, value in update_data.items():
        setattr(document, key, value)
    
    document.updated_at = datetime.utcnow()
    
    # 更新分类
    if category_ids is not None:
        await db.execute(
            DocumentCategory.__table__.delete().where(DocumentCategory.document_id == document_id)
        )
        for cat_id in category_ids:
            db.add(DocumentCategory(document_id=document.id, category_id=cat_id))
    
    await db.commit()
    await db.refresh(document)
    
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", response_model=ResponseBase)
async def delete_document(
    document_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """删除文档（仅管理员）"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 删除存储文件
    if document.file_path:
        await storage_service.delete_file(document.file_path)
    
    await db.delete(document)
    await db.commit()
    
    return ResponseBase(message="文档已删除")


@router.post("/{document_id}/review", response_model=DocumentResponse)
async def review_document(
    document_id: int,
    review: DocumentReview,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """审核文档"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    document.status = review.status
    document.review_comment = review.comment
    document.reviewer_id = current_user.id
    document.reviewed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(document)
    
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """下载文档"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    
    if not document or not document.file_path:
        raise HTTPException(status_code=404, detail="文档或文件不存在")
    
    # 增加下载次数
    document.download_count += 1
    await db.commit()
    
    # 获取下载链接
    download_url = await storage_service.get_download_url(document.file_path)
    
    return {"download_url": download_url, "file_name": document.file_name}
