# 地方志数据智能管理系统 - 集成测试
"""端到端集成测试"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestAuthFlow:
    """认证流程集成测试"""
    
    async def test_complete_auth_flow(self, client: AsyncClient):
        """测试完整认证流程"""
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # 1. 注册
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"flow_test_{unique_id}",
                "email": f"flow_{unique_id}@example.com",
                "password": "Test123456",
                "real_name": "集成测试用户"
            }
        )
        
        assert register_response.status_code in [200, 201]
        
        # 2. 登录
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": f"flow_test_{unique_id}",
                "password": "Test123456",
                "location": {"latitude": 39.9, "longitude": 116.4}
            }
        )
        
        assert login_response.status_code == 200
        token = login_response.json()["data"]["access_token"]
        
        # 3. 访问受保护资源
        headers = {"Authorization": f"Bearer {token}"}
        profile_response = await client.get(
            "/api/v1/users/me",
            headers=headers
        )
        
        assert profile_response.status_code == 200
        
        # 4. 登出
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers=headers
        )
        
        assert logout_response.status_code == 200


class TestDocumentFlow:
    """文档管理流程集成测试"""
    
    async def test_document_lifecycle(self, client: AsyncClient, auth_headers: dict):
        """测试文档完整生命周期"""
        # 1. 创建文档
        create_response = await client.post(
            "/api/v1/documents",
            json={
                "title": "集成测试文档",
                "content": "这是一个用于集成测试的文档内容",
                "region": "浙江省",
                "year": 2024,
                "tags": ["测试", "集成"],
                "upload_type": "manual"
            },
            headers=auth_headers
        )
        
        assert create_response.status_code in [200, 201]
        document_id = create_response.json()["data"]["id"]
        
        # 2. 获取文档详情
        detail_response = await client.get(
            f"/api/v1/documents/{document_id}",
            headers=auth_headers
        )
        
        assert detail_response.status_code == 200
        
        # 3. 更新文档
        update_response = await client.put(
            f"/api/v1/documents/{document_id}",
            json={"title": "更新后的标题"},
            headers=auth_headers
        )
        
        assert update_response.status_code == 200
        
        # 4. 搜索文档
        search_response = await client.get(
            "/api/v1/documents",
            params={"q": "集成测试"},
            headers=auth_headers
        )
        
        assert search_response.status_code == 200
        
        # 5. 删除文档
        delete_response = await client.delete(
            f"/api/v1/documents/{document_id}",
            headers=auth_headers
        )
        
        assert delete_response.status_code == 200


class TestSearchFlow:
    """搜索流程集成测试"""
    
    async def test_multi_mode_search(self, client: AsyncClient, auth_headers: dict):
        """测试多模式搜索"""
        # 1. 关键词搜索
        keyword_response = await client.get(
            "/api/v1/documents",
            params={"q": "地方志"},
            headers=auth_headers
        )
        
        assert keyword_response.status_code == 200
        
        # 2. 标签筛选
        tag_response = await client.get(
            "/api/v1/documents",
            params={"tags": "历史"},
            headers=auth_headers
        )
        
        assert tag_response.status_code == 200
        
        # 3. 组合搜索
        combined_response = await client.get(
            "/api/v1/documents",
            params={
                "q": "文化",
                "region": "浙江省",
                "year_start": 2000,
                "year_end": 2024
            },
            headers=auth_headers
        )
        
        assert combined_response.status_code == 200


class TestAIFlow:
    """AI功能集成测试"""
    
    async def test_ai_chat_with_context(self, client: AsyncClient, auth_headers: dict):
        """测试带上下文的AI对话"""
        from unittest.mock import patch
        
        with patch('app.services.ai_service.AIService.chat') as mock_chat:
            mock_chat.return_value = {"answer": "AI回答", "sources": []}
            
            # 1. 第一轮对话
            response1 = await client.post(
                "/api/v1/ai/chat",
                json={"message": "什么是地方志？"},
                headers=auth_headers
            )
            
            assert response1.status_code == 200
            
            # 2. 继续对话（带上下文）
            session_id = response1.json()["data"].get("session_id", "default")
            
            response2 = await client.post(
                "/api/v1/ai/chat",
                json={
                    "message": "请详细说明",
                    "session_id": session_id
                },
                headers=auth_headers
            )
            
            assert response2.status_code == 200


class TestCategoryManagement:
    """分类管理集成测试"""
    
    async def test_category_hierarchy(self, client: AsyncClient, admin_headers: dict):
        """测试分类层级管理"""
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # 1. 创建一级分类
        level1_response = await client.post(
            "/api/v1/categories",
            json={
                "name": f"一级分类_{unique_id}",
                "code": f"level1_{unique_id}",
                "category_type": "region",
                "level": 1
            },
            headers=admin_headers
        )
        
        assert level1_response.status_code in [200, 201]
        level1_id = level1_response.json()["data"]["id"]
        
        # 2. 创建二级分类
        level2_response = await client.post(
            "/api/v1/categories",
            json={
                "name": f"二级分类_{unique_id}",
                "code": f"level2_{unique_id}",
                "category_type": "region",
                "level": 2,
                "parent_id": level1_id
            },
            headers=admin_headers
        )
        
        assert level2_response.status_code in [200, 201]
        
        # 3. 获取分类树
        tree_response = await client.get(
            "/api/v1/categories/tree",
            headers=admin_headers
        )
        
        assert tree_response.status_code == 200


class TestDataAnalytics:
    """数据分析集成测试"""
    
    async def test_analytics_dashboard(self, client: AsyncClient, auth_headers: dict):
        """测试分析仪表盘"""
        # 1. 总览统计
        overview_response = await client.get(
            "/api/v1/analytics/overview",
            headers=auth_headers
        )
        
        assert overview_response.status_code == 200
        
        # 2. 趋势分析
        trends_response = await client.get(
            "/api/v1/analytics/trends",
            params={"period": "month"},
            headers=auth_headers
        )
        
        assert trends_response.status_code == 200
        
        # 3. 地区分布
        regions_response = await client.get(
            "/api/v1/analytics/regions",
            headers=auth_headers
        )
        
        assert regions_response.status_code == 200


class TestPermissions:
    """权限控制集成测试"""
    
    async def test_role_based_access(self, client: AsyncClient, auth_headers: dict, admin_headers: dict):
        """测试基于角色的访问控制"""
        # 1. 普通用户不能访问用户管理
        user_list_response = await client.get(
            "/api/v1/users",
            headers=auth_headers
        )
        
        assert user_list_response.status_code == 403
        
        # 2. 管理员可以访问
        admin_user_list_response = await client.get(
            "/api/v1/users",
            headers=admin_headers
        )
        
        assert admin_user_list_response.status_code == 200
        
        # 3. 普通用户不能创建分类
        category_response = await client.post(
            "/api/v1/categories",
            json={
                "name": "测试",
                "code": "test_perm",
                "category_type": "other",
                "level": 1
            },
            headers=auth_headers
        )
        
        assert category_response.status_code == 403
