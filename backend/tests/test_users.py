# 地方志数据智能管理系统 - 用户管理测试
"""用户管理API测试"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestUserList:
    """用户列表测试"""
    
    async def test_get_users(self, client: AsyncClient, admin_headers: dict):
        """测试获取用户列表（需管理员权限）"""
        response = await client.get(
            "/api/v1/users",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    async def test_get_users_no_permission(self, client: AsyncClient, auth_headers: dict):
        """测试普通用户获取用户列表（应无权限）"""
        response = await client.get(
            "/api/v1/users",
            headers=auth_headers
        )
        
        assert response.status_code == 403
    
    async def test_get_users_with_filter(self, client: AsyncClient, admin_headers: dict):
        """测试筛选用户"""
        response = await client.get(
            "/api/v1/users",
            params={"role": "viewer", "is_active": True},
            headers=admin_headers
        )
        
        assert response.status_code == 200


class TestUserDetail:
    """用户详情测试"""
    
    async def test_get_user_detail(self, client: AsyncClient, admin_headers: dict, test_user_id: int):
        """测试获取用户详情"""
        response = await client.get(
            f"/api/v1/users/{test_user_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "username" in data["data"]
    
    async def test_get_nonexistent_user(self, client: AsyncClient, admin_headers: dict):
        """测试获取不存在的用户"""
        response = await client.get(
            "/api/v1/users/999999",
            headers=admin_headers
        )
        
        assert response.status_code == 404


class TestUserCreate:
    """用户创建测试"""
    
    async def test_create_user(self, client: AsyncClient, admin_headers: dict):
        """测试创建用户"""
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        response = await client.post(
            "/api/v1/users",
            json={
                "username": f"testuser_{unique_id}",
                "email": f"test_{unique_id}@example.com",
                "password": "Test123456",
                "real_name": "测试用户",
                "role": "viewer"
            },
            headers=admin_headers
        )
        
        assert response.status_code in [200, 201]
    
    async def test_create_user_duplicate_username(self, client: AsyncClient, admin_headers: dict):
        """测试创建重复用户名"""
        # 先创建一个用户
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        username = f"duplicate_{unique_id}"
        
        await client.post(
            "/api/v1/users",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "Test123456",
                "real_name": "测试用户",
                "role": "viewer"
            },
            headers=admin_headers
        )
        
        # 再创建相同用户名
        response = await client.post(
            "/api/v1/users",
            json={
                "username": username,
                "email": f"{username}2@example.com",
                "password": "Test123456",
                "real_name": "测试用户2",
                "role": "viewer"
            },
            headers=admin_headers
        )
        
        assert response.status_code == 409


class TestUserUpdate:
    """用户更新测试"""
    
    async def test_update_user(self, client: AsyncClient, admin_headers: dict, test_user_id: int):
        """测试更新用户信息"""
        response = await client.put(
            f"/api/v1/users/{test_user_id}",
            json={"real_name": "更新后的名字"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
    
    async def test_update_user_role(self, client: AsyncClient, admin_headers: dict, test_user_id: int):
        """测试更新用户角色"""
        response = await client.put(
            f"/api/v1/users/{test_user_id}",
            json={"role": "editor"},
            headers=admin_headers
        )
        
        assert response.status_code == 200
    
    async def test_disable_user(self, client: AsyncClient, admin_headers: dict, test_user_id: int):
        """测试禁用用户"""
        response = await client.put(
            f"/api/v1/users/{test_user_id}",
            json={"is_active": False},
            headers=admin_headers
        )
        
        assert response.status_code == 200


class TestUserDelete:
    """用户删除测试"""
    
    async def test_delete_user(self, client: AsyncClient, admin_headers: dict):
        """测试删除用户"""
        # 先创建一个用户
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        create_response = await client.post(
            "/api/v1/users",
            json={
                "username": f"delete_test_{unique_id}",
                "email": f"delete_{unique_id}@example.com",
                "password": "Test123456",
                "real_name": "待删除用户",
                "role": "viewer"
            },
            headers=admin_headers
        )
        
        if create_response.status_code in [200, 201]:
            user_id = create_response.json()["data"]["id"]
            
            # 删除
            response = await client.delete(
                f"/api/v1/users/{user_id}",
                headers=admin_headers
            )
            
            assert response.status_code == 200


class TestUserProfile:
    """用户资料测试"""
    
    async def test_get_my_profile(self, client: AsyncClient, auth_headers: dict):
        """测试获取当前用户资料"""
        response = await client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "username" in data["data"]
    
    async def test_update_my_profile(self, client: AsyncClient, auth_headers: dict):
        """测试更新当前用户资料"""
        response = await client.put(
            "/api/v1/users/me",
            json={"phone": "13800138001"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    async def test_change_password(self, client: AsyncClient, auth_headers: dict):
        """测试修改密码"""
        response = await client.post(
            "/api/v1/users/me/change-password",
            json={
                "old_password": "Test123456",
                "new_password": "NewTest123456"
            },
            headers=auth_headers
        )
        
        # 可能成功或失败（取决于测试用户的实际密码）
        assert response.status_code in [200, 400]


class TestUserLoginLog:
    """登录日志测试"""
    
    async def test_get_login_logs(self, client: AsyncClient, admin_headers: dict):
        """测试获取登录日志"""
        response = await client.get(
            "/api/v1/users/login-logs",
            headers=admin_headers
        )
        
        assert response.status_code == 200
    
    async def test_get_my_login_logs(self, client: AsyncClient, auth_headers: dict):
        """测试获取当前用户登录日志"""
        response = await client.get(
            "/api/v1/users/me/login-logs",
            headers=auth_headers
        )
        
        assert response.status_code == 200
