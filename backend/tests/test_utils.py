# 地方志数据智能管理系统 - 工具函数测试
"""utils模块测试"""

import pytest
from datetime import datetime, date, timedelta


class TestTextUtils:
    """文本工具测试"""
    
    def test_clean_text(self):
        """测试文本清洗"""
        from app.utils.text import clean_text
        
        text = "  <p>测试文本</p>  \n\t  "
        result = clean_text(text)
        
        assert result == "测试文本"
    
    def test_remove_html_tags(self):
        """测试移除HTML标签"""
        from app.utils.text import remove_html_tags
        
        html = "<div><p>Hello</p><br/><span>World</span></div>"
        result = remove_html_tags(html)
        
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result
    
    def test_truncate_text(self):
        """测试文本截断"""
        from app.utils.text import truncate_text
        
        text = "这是一段很长的文本内容" * 10
        result = truncate_text(text, max_length=20)
        
        assert len(result) <= 20
        assert result.endswith("...")
    
    def test_extract_numbers(self):
        """测试提取数字"""
        from app.utils.text import extract_numbers
        
        text = "价格是123.45元，折扣50%"
        result = extract_numbers(text)
        
        assert "123.45" in result
        assert "50%" in result
    
    def test_mask_sensitive_info(self):
        """测试敏感信息脱敏"""
        from app.utils.text import mask_sensitive_info
        
        text = "手机号：13800138000，邮箱：test@example.com"
        result = mask_sensitive_info(text)
        
        assert "13800138000" not in result
        assert "test@example.com" not in result


class TestFileUtils:
    """文件工具测试"""
    
    def test_get_file_extension(self):
        """测试获取文件扩展名"""
        from app.utils.file import get_file_extension
        
        assert get_file_extension("test.pdf") == ".pdf"
        assert get_file_extension("test.PDF") == ".pdf"
        assert get_file_extension("test") == ""
    
    def test_sanitize_filename(self):
        """测试文件名清洗"""
        from app.utils.file import sanitize_filename
        
        assert sanitize_filename("test<>file.pdf") == "testfile.pdf"
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("...") == "unnamed"
    
    def test_format_file_size(self):
        """测试文件大小格式化"""
        from app.utils.file import format_file_size
        
        assert format_file_size(500) == "500 B"
        assert "KB" in format_file_size(1024)
        assert "MB" in format_file_size(1024 * 1024)
        assert "GB" in format_file_size(1024 * 1024 * 1024)
    
    def test_is_allowed_file(self):
        """测试文件类型检查"""
        from app.utils.file import is_allowed_file
        
        assert is_allowed_file("test.pdf") == True
        assert is_allowed_file("test.docx") == True
        assert is_allowed_file("test.exe") == False
        assert is_allowed_file("test.pdf", allowed_types=["document"]) == True


class TestDatetimeUtils:
    """日期时间工具测试"""
    
    def test_format_datetime(self):
        """测试日期时间格式化"""
        from app.utils.datetime import format_datetime
        
        dt = datetime(2024, 1, 15, 10, 30, 0)
        
        assert format_datetime(dt) == "2024-01-15 10:30:00"
        assert format_datetime(dt, "%Y年%m月%d日") == "2024年01月15日"
        assert format_datetime(None, default="N/A") == "N/A"
    
    def test_parse_datetime(self):
        """测试日期时间解析"""
        from app.utils.datetime import parse_datetime
        
        assert parse_datetime("2024-01-15") is not None
        assert parse_datetime("2024年1月15日") is not None
        assert parse_datetime("invalid") is None
    
    def test_time_ago(self):
        """测试相对时间"""
        from app.utils.datetime import time_ago
        
        now = datetime.now()
        
        assert time_ago(now) == "刚刚"
        assert "分钟前" in time_ago(now - timedelta(minutes=5))
        assert "小时前" in time_ago(now - timedelta(hours=2))
        assert "天前" in time_ago(now - timedelta(days=3))
    
    def test_get_date_range(self):
        """测试日期范围"""
        from app.utils.datetime import get_date_range
        
        start, end = get_date_range("today")
        assert start.date() == date.today()
        
        start, end = get_date_range("this_month")
        assert start.day == 1


class TestCryptoUtils:
    """加密工具测试"""
    
    def test_generate_token(self):
        """测试生成Token"""
        from app.utils.crypto import generate_token
        
        token1 = generate_token()
        token2 = generate_token()
        
        assert len(token1) > 0
        assert token1 != token2
    
    def test_hash_and_verify(self):
        """测试哈希和验证"""
        from app.utils.crypto import hash_string, verify_hash
        
        text = "test_string"
        hashed = hash_string(text)
        
        assert verify_hash(text, hashed) == True
        assert verify_hash("wrong", hashed) == False
    
    def test_encrypt_decrypt(self):
        """测试加密解密"""
        from app.utils.crypto import encrypt_data, decrypt_data
        
        original = "sensitive data"
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)
        
        assert encrypted != original
        assert decrypted == original
    
    def test_mask_string(self):
        """测试字符串遮盖"""
        from app.utils.crypto import mask_string
        
        assert mask_string("13800138000") == "138****8000"
        assert mask_string("abc") == "***"


class TestPaginationUtils:
    """分页工具测试"""
    
    def test_pagination_params(self):
        """测试分页参数"""
        from app.utils.pagination import PaginationParams
        
        params = PaginationParams(page=2, page_size=20)
        
        assert params.offset == 20
        assert params.limit == 20
    
    def test_paginated_response(self):
        """测试分页响应"""
        from app.utils.pagination import PaginatedResponse
        
        response = PaginatedResponse(
            items=[1, 2, 3],
            total=100,
            page=2,
            page_size=20
        )
        
        assert response.pages == 5
        assert response.has_next == True
        assert response.has_prev == True


class TestResponseUtils:
    """响应工具测试"""
    
    def test_success_response(self):
        """测试成功响应"""
        from app.utils.response import success_response
        
        response = success_response(data={"id": 1}, message="创建成功")
        
        assert response["code"] == 200
        assert response["message"] == "创建成功"
        assert response["data"]["id"] == 1
    
    def test_error_response(self):
        """测试错误响应"""
        from app.utils.response import error_response
        
        response = error_response(message="参数错误", code=400)
        
        assert response["code"] == 400
        assert response["message"] == "参数错误"
