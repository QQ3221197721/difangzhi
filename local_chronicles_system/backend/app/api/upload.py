"""
文件上传和AI数据提取API
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import os
import uuid
import hashlib
import aiofiles
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_verified_user
from app.models.models import User, FileUpload, ChronicleRecord
from app.models.schemas import (
    FileUploadResponse, FileProcessingStatus, ManualDataUpload,
    BatchDataUpload, APIResponse, SearchResult
)
from app.services.file_processor import FileProcessorService
from app.services.ai_extractor import AIExtractorService


router = APIRouter(prefix="/upload", tags=["文件上传"])


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


async def calculate_file_hash(file_path: str) -> str:
    """计算文件SHA-256哈希"""
    sha256_hash = hashlib.sha256()
    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(8192):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


@router.post("/file", response_model=FileUploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传地方志文件（PDF/TXT/DOC）
    文件将被AI处理，提取数据并自动分类
    """
    # 验证文件类型
    file_ext = get_file_extension(file.filename)
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。支持的类型: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # 验证文件大小
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大{settings.MAX_FILE_SIZE // 1024 // 1024}MB）"
        )
    
    # 创建上传目录
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)
    
    # 生成唯一文件名
    stored_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(upload_dir, stored_filename)
    
    # 保存文件
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # 计算文件哈希
    file_hash = await calculate_file_hash(file_path)
    
    # 检查重复文件
    result = await db.execute(
        select(FileUpload).where(
            FileUpload.file_hash == file_hash,
            FileUpload.user_id == current_user.id
        )
    )
    existing_file = result.scalar_one_or_none()
    if existing_file:
        os.remove(file_path)  # 删除重复文件
        raise HTTPException(status_code=400, detail="该文件已上传过")
    
    # 创建上传记录
    file_upload = FileUpload(
        user_id=current_user.id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=file_size,
        file_hash=file_hash,
        status="pending"
    )
    
    db.add(file_upload)
    await db.commit()
    await db.refresh(file_upload)
    
    # 后台处理文件
    background_tasks.add_task(
        process_uploaded_file,
        file_upload.id,
        file_path,
        file_ext
    )
    
    return FileUploadResponse(
        id=file_upload.id,
        original_filename=file_upload.original_filename,
        file_type=file_upload.file_type,
        file_size=file_upload.file_size,
        status=file_upload.status,
        created_at=file_upload.created_at
    )


async def process_uploaded_file(file_id: uuid.UUID, file_path: str, file_type: str):
    """后台处理上传的文件"""
    from app.core.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            # 更新状态为处理中
            result = await db.execute(select(FileUpload).where(FileUpload.id == file_id))
            file_upload = result.scalar_one_or_none()
            
            if not file_upload:
                return
            
            file_upload.status = "processing"
            file_upload.processing_started_at = datetime.utcnow()
            await db.commit()
            
            # 提取文本内容
            processor = FileProcessorService()
            extracted_text = await processor.extract_text(file_path, file_type)
            
            # AI分析和数据提取
            ai_service = AIExtractorService()
            analysis_result = await ai_service.extract_chronicle_data(extracted_text)
            
            # 保存提取的记录
            records_count = 0
            for record_data in analysis_result.get("records", []):
                record = ChronicleRecord(
                    title=record_data.get("title", "未命名记录"),
                    content=record_data.get("content"),
                    summary=record_data.get("summary"),
                    region=record_data.get("region"),
                    region_province=record_data.get("region_province"),
                    region_city=record_data.get("region_city"),
                    region_district=record_data.get("region_district"),
                    year=record_data.get("year"),
                    unit=record_data.get("unit"),
                    person=record_data.get("person"),
                    income=record_data.get("income"),
                    income_range=record_data.get("income_range"),
                    work_category=record_data.get("work_category"),
                    tags=record_data.get("tags", {}),
                    numeric_data=record_data.get("numeric_data", {}),
                    source_file_id=file_id,
                    source_type="ai_extracted",
                    confidence_score=record_data.get("confidence", 0.8),
                    created_by=file_upload.user_id
                )
                db.add(record)
                records_count += 1
            
            # 更新文件记录
            file_upload.status = "completed"
            file_upload.processing_completed_at = datetime.utcnow()
            file_upload.extracted_text = extracted_text[:10000]  # 保存前10000字符
            file_upload.ai_analysis_result = analysis_result
            file_upload.records_count = records_count
            
            await db.commit()
            
        except Exception as e:
            file_upload.status = "failed"
            file_upload.error_message = str(e)
            await db.commit()


@router.get("/status/{file_id}", response_model=FileProcessingStatus)
async def get_file_status(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文件处理状态"""
    result = await db.execute(
        select(FileUpload).where(
            FileUpload.id == file_id,
            FileUpload.user_id == current_user.id
        )
    )
    file_upload = result.scalar_one_or_none()
    
    if not file_upload:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileProcessingStatus(
        id=file_upload.id,
        status=file_upload.status,
        records_count=file_upload.records_count,
        error_message=file_upload.error_message,
        processing_started_at=file_upload.processing_started_at,
        processing_completed_at=file_upload.processing_completed_at
    )


@router.post("/manual", response_model=APIResponse)
async def upload_manual_data(
    data: ManualDataUpload,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """手动上传已处理的数据"""
    record = ChronicleRecord(
        title=data.title,
        content=data.content,
        region=data.region,
        region_province=data.region_province,
        region_city=data.region_city,
        region_district=data.region_district,
        year=data.year,
        unit=data.unit,
        person=data.person,
        income=data.income,
        work_category=data.work_category,
        tags=data.tags or {},
        numeric_data=data.numeric_data or {},
        source_type="manual_upload",
        confidence_score=1.0,
        is_verified=True,
        verified_by=current_user.id,
        verified_at=datetime.utcnow(),
        created_by=current_user.id
    )
    
    db.add(record)
    await db.commit()
    await db.refresh(record)
    
    return APIResponse(
        success=True,
        message="数据上传成功",
        data={"record_id": str(record.id)}
    )


@router.post("/batch", response_model=APIResponse)
async def upload_batch_data(
    data: BatchDataUpload,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """批量上传已处理的数据"""
    records_created = 0
    
    for item in data.records:
        record = ChronicleRecord(
            title=item.title,
            content=item.content,
            region=item.region,
            region_province=item.region_province,
            region_city=item.region_city,
            region_district=item.region_district,
            year=item.year,
            unit=item.unit,
            person=item.person,
            income=item.income,
            work_category=item.work_category,
            tags=item.tags or {},
            numeric_data=item.numeric_data or {},
            source_type="manual_upload",
            confidence_score=1.0,
            is_verified=True,
            verified_by=current_user.id,
            verified_at=datetime.utcnow(),
            created_by=current_user.id
        )
        db.add(record)
        records_created += 1
    
    await db.commit()
    
    return APIResponse(
        success=True,
        message=f"成功上传 {records_created} 条数据",
        data={"records_count": records_created}
    )


@router.post("/spreadsheet", response_model=APIResponse)
async def upload_spreadsheet(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """上传Excel/CSV表格文件"""
    file_ext = get_file_extension(file.filename)
    if file_ext not in ['xlsx', 'xls', 'csv']:
        raise HTTPException(status_code=400, detail="仅支持xlsx、xls、csv格式")
    
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大")
    
    # 保存文件
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(current_user.id))
    os.makedirs(upload_dir, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = os.path.join(upload_dir, stored_filename)
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    file_hash = await calculate_file_hash(file_path)
    
    # 创建记录
    file_upload = FileUpload(
        user_id=current_user.id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=len(content),
        file_hash=file_hash,
        status="pending"
    )
    
    db.add(file_upload)
    await db.commit()
    await db.refresh(file_upload)
    
    # 后台处理表格
    background_tasks.add_task(
        process_spreadsheet,
        file_upload.id,
        file_path,
        file_ext,
        current_user.id
    )
    
    return APIResponse(
        success=True,
        message="表格已上传，正在处理中",
        data={"file_id": str(file_upload.id)}
    )


async def process_spreadsheet(
    file_id: uuid.UUID, 
    file_path: str, 
    file_type: str,
    user_id: uuid.UUID
):
    """处理表格文件"""
    import pandas as pd
    from app.core.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(FileUpload).where(FileUpload.id == file_id))
            file_upload = result.scalar_one_or_none()
            
            if not file_upload:
                return
            
            file_upload.status = "processing"
            file_upload.processing_started_at = datetime.utcnow()
            await db.commit()
            
            # 读取表格
            if file_type == 'csv':
                df = pd.read_csv(file_path, encoding='utf-8')
            else:
                df = pd.read_excel(file_path)
            
            # 列名映射
            column_mapping = {
                '标题': 'title',
                '内容': 'content',
                '地区': 'region',
                '省份': 'region_province',
                '城市': 'region_city',
                '区县': 'region_district',
                '年份': 'year',
                '单位': 'unit',
                '人物': 'person',
                '收入': 'income',
                '工作类别': 'work_category',
            }
            
            df = df.rename(columns=column_mapping)
            
            records_count = 0
            for _, row in df.iterrows():
                record = ChronicleRecord(
                    title=str(row.get('title', '未命名')),
                    content=str(row.get('content', '')) if pd.notna(row.get('content')) else None,
                    region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                    region_province=str(row.get('region_province', '')) if pd.notna(row.get('region_province')) else None,
                    region_city=str(row.get('region_city', '')) if pd.notna(row.get('region_city')) else None,
                    region_district=str(row.get('region_district', '')) if pd.notna(row.get('region_district')) else None,
                    year=int(row.get('year')) if pd.notna(row.get('year')) else None,
                    unit=str(row.get('unit', '')) if pd.notna(row.get('unit')) else None,
                    person=str(row.get('person', '')) if pd.notna(row.get('person')) else None,
                    income=float(row.get('income')) if pd.notna(row.get('income')) else None,
                    work_category=str(row.get('work_category', '')) if pd.notna(row.get('work_category')) else None,
                    source_file_id=file_id,
                    source_type="spreadsheet_upload",
                    confidence_score=1.0,
                    created_by=user_id
                )
                db.add(record)
                records_count += 1
            
            file_upload.status = "completed"
            file_upload.processing_completed_at = datetime.utcnow()
            file_upload.records_count = records_count
            
            await db.commit()
            
        except Exception as e:
            file_upload.status = "failed"
            file_upload.error_message = str(e)
            await db.commit()


@router.get("/history", response_model=List[FileUploadResponse])
async def get_upload_history(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20
):
    """获取上传历史"""
    offset = (page - 1) * page_size
    result = await db.execute(
        select(FileUpload)
        .where(FileUpload.user_id == current_user.id)
        .order_by(FileUpload.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    files = result.scalars().all()
    
    return [
        FileUploadResponse(
            id=f.id,
            original_filename=f.original_filename,
            file_type=f.file_type,
            file_size=f.file_size,
            status=f.status,
            created_at=f.created_at
        )
        for f in files
    ]
