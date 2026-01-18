"""
地方志系统 - 文档 API 测试
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_document_manual(client: AsyncClient):
    """测试手动创建文档"""
    # 先注册并登录
    await client.post("/api/v1/auth/register", json={
        "username": "doctest",
        "email": "doctest@example.com",
        "password": "Test123456",
        "real_name": "文档测试"
    })
    
    login_response = await client.post("/api/v1/auth/login", json={
        "username": "doctest",
        "password": "Test123456",
        "location": {"latitude": 39.9, "longitude": 116.4}
    })
    token = login_response.json()["access_token"]
    
    # 创建文档
    response = await client.post(
        "/api/v1/documents/manual",
        json={
            "title": "测试地方志文档",
            "content": "这是一个测试内容",
            "region": "北京市",
            "year": 2024,
            "tags": ["测试", "地方志"]
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "测试地方志文档"


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient):
    """测试获取文档列表"""
    # 登录
    await client.post("/api/v1/auth/register", json={
        "username": "listtest",
        "email": "listtest@example.com",
        "password": "Test123456",
        "real_name": "列表测试"
    })
    
    login_response = await client.post("/api/v1/auth/login", json={
        "username": "listtest",
        "password": "Test123456",
        "location": {"latitude": 39.9, "longitude": 116.4}
    })
    token = login_response.json()["access_token"]
    
    # 获取列表
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_search_documents(client: AsyncClient):
    """测试搜索文档"""
    # 登录
    await client.post("/api/v1/auth/register", json={
        "username": "searchtest",
        "email": "searchtest@example.com",
        "password": "Test123456",
        "real_name": "搜索测试"
    })
    
    login_response = await client.post("/api/v1/auth/login", json={
        "username": "searchtest",
        "password": "Test123456",
        "location": {"latitude": 39.9, "longitude": 116.4}
    })
    token = login_response.json()["access_token"]
    
    # 搜索
    response = await client.get(
        "/api/v1/documents",
        params={"keyword": "测试"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
