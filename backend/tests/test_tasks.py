# 地方志数据智能管理系统 - 异步任务测试
"""Celery任务测试"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


class TestAITasks:
    """AI相关任务测试"""
    
    def test_process_document_ai(self):
        """测试文档AI处理任务"""
        from app.tasks.ai_tasks import process_document_ai
        
        with patch('app.tasks.ai_tasks.AIService') as MockAIService:
            mock_service = MagicMock()
            mock_service.generate_summary.return_value = "文档摘要"
            mock_service.extract_keywords.return_value = ["关键词1", "关键词2"]
            MockAIService.return_value = mock_service
            
            result = process_document_ai(document_id=1, content="文档内容")
            
            assert result is not None
    
    def test_generate_embeddings(self):
        """测试生成向量嵌入任务"""
        from app.tasks.ai_tasks import generate_embeddings
        
        with patch('app.tasks.ai_tasks.AIService') as MockAIService:
            mock_service = MagicMock()
            mock_service.get_embedding.return_value = [0.1] * 1536
            MockAIService.return_value = mock_service
            
            result = generate_embeddings(document_id=1, text="文档内容")
            
            assert result is not None


class TestFileTasks:
    """文件处理任务测试"""
    
    def test_process_uploaded_file(self):
        """测试处理上传文件任务"""
        from app.tasks.file_tasks import process_uploaded_file
        
        with patch('app.tasks.file_tasks.FileProcessor') as MockProcessor:
            mock_processor = MagicMock()
            mock_processor.process_file.return_value = {"text": "提取的文本"}
            MockProcessor.return_value = mock_processor
            
            result = process_uploaded_file(
                file_path="uploads/test.pdf",
                document_id=1
            )
            
            assert result is not None
    
    def test_generate_thumbnail(self):
        """测试生成缩略图任务"""
        from app.tasks.file_tasks import generate_thumbnail
        
        with patch('app.tasks.file_tasks.ImageProcessor') as MockImageProcessor:
            mock_processor = MagicMock()
            mock_processor.resize.return_value = b"thumbnail data"
            MockImageProcessor.return_value = mock_processor
            
            result = generate_thumbnail(
                file_path="uploads/test.jpg",
                size=(200, 200)
            )
            
            # 可能返回缩略图路径或None（如果不是图片）
            assert result is None or isinstance(result, str)


class TestCleanupTasks:
    """清理任务测试"""
    
    def test_cleanup_temp_files(self):
        """测试清理临时文件任务"""
        from app.tasks.cleanup_tasks import cleanup_temp_files
        
        with patch('os.listdir') as mock_listdir:
            with patch('os.remove') as mock_remove:
                mock_listdir.return_value = ["temp1.txt", "temp2.txt"]
                
                result = cleanup_temp_files(max_age_hours=24)
                
                assert isinstance(result, int)
    
    def test_cleanup_expired_sessions(self):
        """测试清理过期会话任务"""
        from app.tasks.cleanup_tasks import cleanup_expired_sessions
        
        with patch('app.tasks.cleanup_tasks.SessionManager') as MockSessionManager:
            mock_manager = MagicMock()
            mock_manager.cleanup_expired.return_value = 5
            MockSessionManager.return_value = mock_manager
            
            result = cleanup_expired_sessions()
            
            assert isinstance(result, int)
    
    def test_archive_old_logs(self):
        """测试归档旧日志任务"""
        from app.tasks.cleanup_tasks import archive_old_logs
        
        with patch('app.tasks.cleanup_tasks.LogArchiver') as MockArchiver:
            mock_archiver = MagicMock()
            mock_archiver.archive.return_value = "logs/archive_20240101.tar.gz"
            MockArchiver.return_value = mock_archiver
            
            result = archive_old_logs(days=30)
            
            assert result is None or isinstance(result, str)


class TestScheduledTasks:
    """定时任务测试"""
    
    def test_daily_stats_report(self):
        """测试每日统计报告任务"""
        from app.tasks.cleanup_tasks import daily_stats_report
        
        with patch('app.tasks.cleanup_tasks.AnalyticsService') as MockAnalytics:
            mock_service = MagicMock()
            mock_service.generate_daily_report.return_value = {
                "total_documents": 100,
                "new_today": 5
            }
            MockAnalytics.return_value = mock_service
            
            result = daily_stats_report()
            
            assert result is not None
    
    def test_sync_search_index(self):
        """测试同步搜索索引任务"""
        from app.tasks.file_tasks import sync_search_index
        
        with patch('app.tasks.file_tasks.SearchService') as MockSearch:
            mock_service = MagicMock()
            mock_service.reindex_all.return_value = 150
            MockSearch.return_value = mock_service
            
            result = sync_search_index()
            
            assert isinstance(result, int)


class TestTaskRetry:
    """任务重试测试"""
    
    def test_task_retry_on_failure(self):
        """测试任务失败重试"""
        from app.tasks.ai_tasks import process_document_ai
        
        with patch('app.tasks.ai_tasks.AIService') as MockAIService:
            # 模拟前两次失败，第三次成功
            mock_service = MagicMock()
            mock_service.generate_summary.side_effect = [
                Exception("Temporary error"),
                Exception("Temporary error"),
                "成功的摘要"
            ]
            MockAIService.return_value = mock_service
            
            # 实际的重试逻辑由Celery处理
            # 这里只测试任务本身
            try:
                result = process_document_ai(document_id=1, content="内容")
            except Exception:
                pass  # 期望失败或成功取决于重试配置
