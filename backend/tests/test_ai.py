# 地方志数据智能管理系统 - AI服务测试
"""AI相关API测试"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio


class TestAIChat:
    """AI对话测试"""
    
    async def test_chat_success(self, client: AsyncClient, auth_headers: dict):
        """测试AI对话成功"""
        with patch('app.services.ai_service.AIService.chat') as mock_chat:
            mock_chat.return_value = {
                "answer": "这是AI的回答",
                "sources": []
            }
            
            response = await client.post(
                "/api/v1/ai/chat",
                json={"message": "测试问题"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "answer" in data["data"]
    
    async def test_chat_empty_message(self, client: AsyncClient, auth_headers: dict):
        """测试空消息"""
        response = await client.post(
            "/api/v1/ai/chat",
            json={"message": ""},
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    async def test_chat_unauthorized(self, client: AsyncClient):
        """测试未授权访问"""
        response = await client.post(
            "/api/v1/ai/chat",
            json={"message": "测试"}
        )
        
        assert response.status_code == 401


class TestAISummary:
    """AI摘要测试"""
    
    async def test_generate_summary(self, client: AsyncClient, auth_headers: dict):
        """测试生成摘要"""
        with patch('app.services.ai_service.AIService.generate_summary') as mock_summary:
            mock_summary.return_value = "这是文档摘要"
            
            response = await client.post(
                "/api/v1/ai/summary",
                json={"content": "这是一段很长的文本内容" * 100},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200


class TestAIKeywords:
    """AI关键词提取测试"""
    
    async def test_extract_keywords(self, client: AsyncClient, auth_headers: dict):
        """测试提取关键词"""
        with patch('app.services.ai_service.AIService.extract_keywords') as mock_extract:
            mock_extract.return_value = ["地方志", "历史", "文化"]
            
            response = await client.post(
                "/api/v1/ai/keywords",
                json={"content": "地方志是记录地方历史文化的重要文献"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "keywords" in data["data"]


class TestAISearch:
    """AI语义搜索测试"""
    
    async def test_semantic_search(self, client: AsyncClient, auth_headers: dict):
        """测试语义搜索"""
        with patch('app.services.ai_service.AIService.semantic_search') as mock_search:
            mock_search.return_value = []
            
            response = await client.get(
                "/api/v1/ai/search",
                params={"q": "明清时期的地方志"},
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200


class TestChatHistory:
    """对话历史测试"""
    
    async def test_get_chat_history(self, client: AsyncClient, auth_headers: dict):
        """测试获取对话历史"""
        response = await client.get(
            "/api/v1/ai/history",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    async def test_clear_chat_history(self, client: AsyncClient, auth_headers: dict):
        """测试清空对话历史"""
        response = await client.delete(
            "/api/v1/ai/history",
            headers=auth_headers
        )
        
        assert response.status_code == 200
