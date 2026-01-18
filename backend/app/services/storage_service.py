"""
地方志数据智能管理系统 - 存储服务
"""
import os
from typing import Optional
from datetime import timedelta

from minio import Minio
from minio.error import S3Error
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class StorageService:
    """对象存储服务 (MinIO/S3)"""
    
    def __init__(self):
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to create bucket: {e}")
    
    async def upload_file(
        self,
        file_path: str,
        content: bytes,
        content_type: Optional[str] = None
    ) -> str:
        """上传文件"""
        try:
            from io import BytesIO
            data = BytesIO(content)
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=file_path,
                data=data,
                length=len(content),
                content_type=content_type or "application/octet-stream"
            )
            logger.info(f"Uploaded file: {file_path}")
            return file_path
        except S3Error as e:
            logger.error(f"Failed to upload file: {e}")
            raise
    
    async def download_file(self, file_path: str) -> bytes:
        """下载文件"""
        try:
            response = self.client.get_object(self.bucket, file_path)
            content = response.read()
            response.close()
            response.release_conn()
            return content
        except S3Error as e:
            logger.error(f"Failed to download file: {e}")
            raise
    
    async def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            self.client.remove_object(self.bucket, file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    async def get_download_url(
        self,
        file_path: str,
        expires: int = 3600
    ) -> str:
        """获取下载链接"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=file_path,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise
    
    async def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        try:
            self.client.stat_object(self.bucket, file_path)
            return True
        except S3Error:
            return False
    
    async def list_files(self, prefix: str = "") -> list:
        """列出文件"""
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"Failed to list files: {e}")
            return []


# 单例实例
storage_service = StorageService()
