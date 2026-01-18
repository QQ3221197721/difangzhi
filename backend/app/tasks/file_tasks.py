"""
文件处理异步任务
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import datetime
import uuid

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_uploaded_file_task(self, file_id: str, file_path: str, file_type: str, user_id: str):
    """
    异步处理上传的文件
    - 提取文本
    - AI分析
    - 存储结果
    """
    from app.celery_app import run_async
    from app.services.file_processor import FileProcessorService
    from app.services.ai_extractor import AIExtractorService
    from app.core.database import AsyncSessionLocal
    from app.models.models import FileUpload, ChronicleRecord
    from sqlalchemy import select
    
    async def _process():
        async with AsyncSessionLocal() as db:
            try:
                # 获取文件记录
                result = await db.execute(
                    select(FileUpload).where(FileUpload.id == uuid.UUID(file_id))
                )
                file_upload = result.scalar_one_or_none()
                
                if not file_upload:
                    logger.error(f"文件不存在: {file_id}")
                    return {"status": "error", "message": "文件不存在"}
                
                # 更新状态
                file_upload.status = "processing"
                file_upload.processing_started_at = datetime.utcnow()
                await db.commit()
                
                logger.info(f"开始处理文件: {file_upload.original_filename}")
                
                # 提取文本
                processor = FileProcessorService()
                extracted_text = await processor.extract_text(file_path, file_type)
                
                if not extracted_text or len(extracted_text) < 10:
                    raise ValueError("提取的文本内容过少")
                
                logger.info(f"文本提取完成，长度: {len(extracted_text)}")
                
                # AI分析
                ai_service = AIExtractorService()
                analysis_result = await ai_service.extract_chronicle_data(extracted_text)
                
                # 保存提取的记录
                records_count = 0
                for record_data in analysis_result.get("records", []):
                    record = ChronicleRecord(
                        title=record_data.get("title", "未命名记录")[:500],
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
                        source_file_id=uuid.UUID(file_id),
                        source_type="ai_extracted",
                        confidence_score=record_data.get("confidence", 0.8),
                        created_by=uuid.UUID(user_id)
                    )
                    db.add(record)
                    records_count += 1
                
                # 更新文件状态
                file_upload.status = "completed"
                file_upload.processing_completed_at = datetime.utcnow()
                file_upload.extracted_text = extracted_text[:10000]
                file_upload.ai_analysis_result = analysis_result
                file_upload.records_count = records_count
                
                await db.commit()
                
                logger.info(f"文件处理完成，提取 {records_count} 条记录")
                return {"status": "success", "records_count": records_count}
                
            except Exception as e:
                logger.error(f"文件处理失败: {e}")
                file_upload.status = "failed"
                file_upload.error_message = str(e)[:500]
                await db.commit()
                raise
    
    try:
        return run_async(_process())
    except Exception as exc:
        logger.error(f"任务失败，准备重试: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def process_spreadsheet_task(self, file_id: str, file_path: str, file_type: str, user_id: str):
    """异步处理表格文件"""
    import pandas as pd
    from app.celery_app import run_async
    from app.core.database import AsyncSessionLocal
    from app.models.models import FileUpload, ChronicleRecord
    from sqlalchemy import select
    
    async def _process():
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(FileUpload).where(FileUpload.id == uuid.UUID(file_id))
                )
                file_upload = result.scalar_one_or_none()
                
                if not file_upload:
                    return {"status": "error", "message": "文件不存在"}
                
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
                    '标题': 'title', '内容': 'content', '地区': 'region',
                    '省份': 'region_province', '城市': 'region_city',
                    '区县': 'region_district', '年份': 'year',
                    '单位': 'unit', '人物': 'person',
                    '收入': 'income', '工作类别': 'work_category',
                }
                df = df.rename(columns=column_mapping)
                
                records_count = 0
                for _, row in df.iterrows():
                    record = ChronicleRecord(
                        title=str(row.get('title', '未命名'))[:500],
                        content=str(row.get('content', '')) if pd.notna(row.get('content')) else None,
                        region=str(row.get('region', '')) if pd.notna(row.get('region')) else None,
                        region_province=str(row.get('region_province', '')) if pd.notna(row.get('region_province')) else None,
                        region_city=str(row.get('region_city', '')) if pd.notna(row.get('region_city')) else None,
                        year=int(row.get('year')) if pd.notna(row.get('year')) else None,
                        unit=str(row.get('unit', '')) if pd.notna(row.get('unit')) else None,
                        person=str(row.get('person', '')) if pd.notna(row.get('person')) else None,
                        income=float(row.get('income')) if pd.notna(row.get('income')) else None,
                        work_category=str(row.get('work_category', '')) if pd.notna(row.get('work_category')) else None,
                        source_file_id=uuid.UUID(file_id),
                        source_type="spreadsheet_upload",
                        confidence_score=1.0,
                        created_by=uuid.UUID(user_id)
                    )
                    db.add(record)
                    records_count += 1
                
                file_upload.status = "completed"
                file_upload.processing_completed_at = datetime.utcnow()
                file_upload.records_count = records_count
                await db.commit()
                
                return {"status": "success", "records_count": records_count}
                
            except Exception as e:
                logger.error(f"表格处理失败: {e}")
                file_upload.status = "failed"
                file_upload.error_message = str(e)[:500]
                await db.commit()
                raise
    
    try:
        return run_async(_process())
    except Exception as exc:
        raise self.retry(exc=exc)
