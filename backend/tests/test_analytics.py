# 地方志数据智能管理系统 - 分析服务测试
"""数据分析API测试"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch

pytestmark = pytest.mark.asyncio


class TestDashboard:
    """仪表盘统计测试"""
    
    async def test_get_overview(self, client: AsyncClient, auth_headers: dict):
        """测试获取总览统计"""
        response = await client.get(
            "/api/v1/analytics/overview",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
    
    async def test_get_trends(self, client: AsyncClient, auth_headers: dict):
        """测试获取趋势数据"""
        response = await client.get(
            "/api/v1/analytics/trends",
            params={"period": "month"},
            headers=auth_headers
        )
        
        assert response.status_code == 200


class TestRegionAnalytics:
    """地区统计测试"""
    
    async def test_get_region_distribution(self, client: AsyncClient, auth_headers: dict):
        """测试获取地区分布"""
        response = await client.get(
            "/api/v1/analytics/regions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    async def test_get_region_detail(self, client: AsyncClient, auth_headers: dict):
        """测试获取地区详情"""
        response = await client.get(
            "/api/v1/analytics/regions/浙江省",
            headers=auth_headers
        )
        
        assert response.status_code == 200


class TestTimeAnalytics:
    """时间统计测试"""
    
    async def test_get_year_distribution(self, client: AsyncClient, auth_headers: dict):
        """测试获取年份分布"""
        response = await client.get(
            "/api/v1/analytics/years",
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    async def test_get_upload_trends(self, client: AsyncClient, auth_headers: dict):
        """测试获取上传趋势"""
        response = await client.get(
            "/api/v1/analytics/uploads",
            params={"days": 30},
            headers=auth_headers
        )
        
        assert response.status_code == 200


class TestCategoryAnalytics:
    """分类统计测试"""
    
    async def test_get_category_distribution(self, client: AsyncClient, auth_headers: dict):
        """测试获取分类分布"""
        response = await client.get(
            "/api/v1/analytics/categories",
            headers=auth_headers
        )
        
        assert response.status_code == 200
    
    async def test_get_tag_cloud(self, client: AsyncClient, auth_headers: dict):
        """测试获取标签云"""
        response = await client.get(
            "/api/v1/analytics/tags",
            params={"limit": 50},
            headers=auth_headers
        )
        
        assert response.status_code == 200


class TestUserAnalytics:
    """用户统计测试"""
    
    async def test_get_user_activity(self, client: AsyncClient, admin_headers: dict):
        """测试获取用户活动统计（需管理员权限）"""
        response = await client.get(
            "/api/v1/analytics/users/activity",
            headers=admin_headers
        )
        
        assert response.status_code == 200
    
    async def test_get_top_uploaders(self, client: AsyncClient, auth_headers: dict):
        """测试获取上传排行"""
        response = await client.get(
            "/api/v1/analytics/users/top-uploaders",
            params={"limit": 10},
            headers=auth_headers
        )
        
        assert response.status_code == 200


class TestExport:
    """数据导出测试"""
    
    async def test_export_report(self, client: AsyncClient, auth_headers: dict):
        """测试导出报告"""
        response = await client.get(
            "/api/v1/analytics/export",
            params={"format": "xlsx"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "application" in response.headers.get("content-type", "")
