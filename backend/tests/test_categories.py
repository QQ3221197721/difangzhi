# 地方志数据智能管理系统 - 分类管理测试
"""分类相关API测试"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestCategoryList:
    """分类列表测试"""
    
    async def test_get_categories(self, client: AsyncClient, auth_headers: dict):
        """测试获取分类列表"""
        response = await client.get(
            "/api/v1/categories",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    async def test_get_categories_by_type(self, client: AsyncClient, auth_headers: dict):
        """测试按类型获取分类"""
        response = await client.get(
            "/api/v1/categories",
            params={"type": "region"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    async def test_get_category_tree(self, client: AsyncClient, auth_headers: dict):
        """测试获取分类树"""
        response = await client.get(
            "/api/v1/categories/tree",
            headers=auth_headers
        )
        
        assert response.status_code == 200


class TestCategoryCreate:
    """分类创建测试"""
    
    async def test_create_category(self, client: AsyncClient, admin_headers: dict):
        """测试创建分类（需管理员权限）"""
        response = await client.post(
            "/api/v1/categories",
            json={
                "name": "测试分类",
                "code": "test_category",
                "category_type": "other",
                "level": 1
            },
            headers=admin_headers
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["code"] in [200, 201]
    
    async def test_create_category_duplicate_code(self, client: AsyncClient, admin_headers: dict):
        """测试创建重复编码的分类"""
        # 先创建一个
        await client.post(
            "/api/v1/categories",
            json={
                "name": "分类A",
                "code": "duplicate_test",
                "category_type": "other",
                "level": 1
            },
            headers=admin_headers
        )
        
        # 再创建相同编码的
        response = await client.post(
            "/api/v1/categories",
            json={
                "name": "分类B",
                "code": "duplicate_test",
                "category_type": "other",
                "level": 1
            },
            headers=admin_headers
        )
        
        assert response.status_code == 409  # Conflict
    
    async def test_create_subcategory(self, client: AsyncClient, admin_headers: dict):
        """测试创建子分类"""
        # 先创建父分类
        parent_response = await client.post(
            "/api/v1/categories",
            json={
                "name": "父分类",
                "code": "parent_cat",
                "category_type": "region",
                "level": 1
            },
            headers=admin_headers
        )
        
        if parent_response.status_code in [200, 201]:
            parent_id = parent_response.json()["data"]["id"]
            
            # 创建子分类
            response = await client.post(
                "/api/v1/categories",
                json={
                    "name": "子分类",
                    "code": "child_cat",
                    "category_type": "region",
                    "level": 2,
                    "parent_id": parent_id
                },
                headers=admin_headers
            )
            
            assert response.status_code in [200, 201]


class TestCategoryUpdate:
    """分类更新测试"""
    
    async def test_update_category(self, client: AsyncClient, admin_headers: dict):
        """测试更新分类"""
        # 先创建
        create_response = await client.post(
            "/api/v1/categories",
            json={
                "name": "待更新分类",
                "code": "update_test",
                "category_type": "other",
                "level": 1
            },
            headers=admin_headers
        )
        
        if create_response.status_code in [200, 201]:
            category_id = create_response.json()["data"]["id"]
            
            # 更新
            response = await client.put(
                f"/api/v1/categories/{category_id}",
                json={"name": "已更新分类"},
                headers=admin_headers
            )
            
            assert response.status_code == 200


class TestCategoryDelete:
    """分类删除测试"""
    
    async def test_delete_category(self, client: AsyncClient, admin_headers: dict):
        """测试删除分类"""
        # 先创建
        create_response = await client.post(
            "/api/v1/categories",
            json={
                "name": "待删除分类",
                "code": "delete_test",
                "category_type": "other",
                "level": 1
            },
            headers=admin_headers
        )
        
        if create_response.status_code in [200, 201]:
            category_id = create_response.json()["data"]["id"]
            
            # 删除
            response = await client.delete(
                f"/api/v1/categories/{category_id}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
    
    async def test_delete_category_with_documents(self, client: AsyncClient, admin_headers: dict):
        """测试删除有关联文档的分类（应失败）"""
        # 这个测试需要先创建分类并关联文档
        pass  # 具体实现依赖于测试数据准备


class TestCategoryPermissions:
    """分类权限测试"""
    
    async def test_create_category_no_permission(self, client: AsyncClient, auth_headers: dict):
        """测试普通用户创建分类（应无权限）"""
        response = await client.post(
            "/api/v1/categories",
            json={
                "name": "测试",
                "code": "no_perm_test",
                "category_type": "other",
                "level": 1
            },
            headers=auth_headers
        )
        
        assert response.status_code == 403
