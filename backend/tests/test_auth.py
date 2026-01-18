"""
地方志系统 - 认证 API 测试
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    """测试用户注册"""
    response = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "Test123456",
        "real_name": "测试用户"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    """测试用户登录"""
    # 先注册
    await client.post("/api/v1/auth/register", json={
        "username": "logintest",
        "email": "login@example.com",
        "password": "Test123456",
        "real_name": "登录测试"
    })
    
    # 登录
    response = await client.post("/api/v1/auth/login", json={
        "username": "logintest",
        "password": "Test123456",
        "location": {"latitude": 39.9, "longitude": 116.4}
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """测试健康检查"""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
