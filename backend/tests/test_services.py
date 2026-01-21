# 地方志数据智能管理系统 - 服务层测试
"""业务服务测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

pytestmark = pytest.mark.asyncio


class TestAIService:
    """AI服务测试"""
    
    async def test_generate_summary(self):
        """测试生成摘要"""
        from app.services.ai_service import AIService
        
        with patch.object(AIService, '_call_openai') as mock_call:
            mock_call.return_value = "这是生成的摘要"
            
            service = AIService()
            result = await service.generate_summary("很长的文本内容" * 100)
            
            assert result is not None
            assert len(result) > 0
    
    async def test_extract_keywords(self):
        """测试提取关键词"""
        from app.services.ai_service import AIService
        
        service = AIService()
        
        with patch.object(service, '_call_openai') as mock_call:
            mock_call.return_value = '["地方志", "历史", "文化"]'
            
            result = await service.extract_keywords("地方志是记录地方历史文化的重要文献")
            
            assert isinstance(result, list)


class TestCacheService:
    """缓存服务测试"""
    
    async def test_set_and_get(self):
        """测试设置和获取缓存"""
        from app.services.cache_service import CacheService
        
        service = CacheService()
        
        with patch.object(service, 'redis') as mock_redis:
            mock_redis.set = AsyncMock()
            mock_redis.get = AsyncMock(return_value=b'{"test": "value"}')
            
            await service.set("test_key", {"test": "value"})
            result = await service.get("test_key")
            
            assert result == {"test": "value"}
    
    async def test_delete(self):
        """测试删除缓存"""
        from app.services.cache_service import CacheService
        
        service = CacheService()
        
        with patch.object(service, 'redis') as mock_redis:
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await service.delete("test_key")
            
            assert result == True


class TestFileProcessor:
    """文件处理服务测试"""
    
    async def test_process_pdf(self):
        """测试处理PDF文件"""
        from app.services.file_processor import FileProcessor
        
        processor = FileProcessor()
        
        # Mock PDF处理
        with patch.object(processor, '_extract_pdf_text') as mock_extract:
            mock_extract.return_value = "提取的PDF文本内容"
            
            result = await processor.process_file("test.pdf", b"fake pdf content")
            
            assert "text" in result
    
    async def test_process_excel(self):
        """测试处理Excel文件"""
        from app.services.file_processor import FileProcessor
        
        processor = FileProcessor()
        
        with patch.object(processor, '_extract_excel_data') as mock_extract:
            mock_extract.return_value = [{"col1": "val1"}]
            
            result = await processor.process_file("test.xlsx", b"fake excel content")
            
            assert "data" in result
    
    async def test_unsupported_file_type(self):
        """测试不支持的文件类型"""
        from app.services.file_processor import FileProcessor
        
        processor = FileProcessor()
        
        with pytest.raises(ValueError):
            await processor.process_file("test.xyz", b"content")


class TestStorageService:
    """存储服务测试"""
    
    async def test_upload_file(self):
        """测试上传文件"""
        from app.services.storage_service import StorageService
        
        service = StorageService()
        
        with patch.object(service, 'client') as mock_client:
            mock_client.put_object = MagicMock()
            
            result = await service.upload_file(
                bucket="test-bucket",
                key="test/file.pdf",
                data=b"file content"
            )
            
            assert result is not None
    
    async def test_download_file(self):
        """测试下载文件"""
        from app.services.storage_service import StorageService
        
        service = StorageService()
        
        with patch.object(service, 'client') as mock_client:
            mock_response = MagicMock()
            mock_response.read.return_value = b"file content"
            mock_client.get_object = MagicMock(return_value=mock_response)
            
            result = await service.download_file(
                bucket="test-bucket",
                key="test/file.pdf"
            )
            
            assert result == b"file content"
    
    async def test_delete_file(self):
        """测试删除文件"""
        from app.services.storage_service import StorageService
        
        service = StorageService()
        
        with patch.object(service, 'client') as mock_client:
            mock_client.remove_object = MagicMock()
            
            result = await service.delete_file(
                bucket="test-bucket",
                key="test/file.pdf"
            )
            
            assert result == True


class TestSecurityService:
    """安全服务测试"""
    
    def test_hash_password(self):
        """测试密码哈希"""
        from app.core.security import hash_password, verify_password
        
        password = "TestPassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword", hashed)
    
    def test_create_token(self):
        """测试创建Token"""
        from app.core.security import create_access_token
        
        token = create_access_token(data={"sub": "test_user"})
        
        assert token is not None
        assert len(token) > 0
    
    def test_decode_token(self):
        """测试解码Token"""
        from app.core.security import create_access_token, decode_token
        
        token = create_access_token(data={"sub": "test_user"})
        payload = decode_token(token)
        
        assert payload is not None
        assert payload.get("sub") == "test_user"
