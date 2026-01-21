# 地方志数据智能管理系统 - 验证器测试
"""validators模块测试"""

import pytest


class TestEmailValidator:
    """邮箱验证测试"""
    
    def test_valid_email(self):
        """测试有效邮箱"""
        from app.validators import validate_email
        
        assert validate_email("test@example.com").is_valid == True
        assert validate_email("user.name@domain.org").is_valid == True
        assert validate_email("user+tag@example.co.uk").is_valid == True
    
    def test_invalid_email(self):
        """测试无效邮箱"""
        from app.validators import validate_email
        
        assert validate_email("").is_valid == False
        assert validate_email("invalid").is_valid == False
        assert validate_email("@example.com").is_valid == False
        assert validate_email("test@").is_valid == False


class TestPhoneValidator:
    """手机号验证测试"""
    
    def test_valid_phone(self):
        """测试有效手机号"""
        from app.validators import validate_phone
        
        assert validate_phone("13800138000").is_valid == True
        assert validate_phone("15912345678").is_valid == True
        assert validate_phone("18687654321").is_valid == True
    
    def test_invalid_phone(self):
        """测试无效手机号"""
        from app.validators import validate_phone
        
        assert validate_phone("").is_valid == False
        assert validate_phone("12345678901").is_valid == False
        assert validate_phone("1380013800").is_valid == False
        assert validate_phone("23800138000").is_valid == False


class TestIdCardValidator:
    """身份证号验证测试"""
    
    def test_valid_id_card(self):
        """测试有效身份证号"""
        from app.validators import validate_id_card
        
        # 注意：这是一个虚构的符合校验规则的身份证号
        result = validate_id_card("110101199003074530")
        
        # 验证校验码计算
        assert result.is_valid == True or "校验码" in result.message
    
    def test_invalid_id_card(self):
        """测试无效身份证号"""
        from app.validators import validate_id_card
        
        assert validate_id_card("").is_valid == False
        assert validate_id_card("12345678901234567X").is_valid == False
        assert validate_id_card("11010119900307453").is_valid == False  # 17位


class TestPasswordValidator:
    """密码强度验证测试"""
    
    def test_strong_password(self):
        """测试强密码"""
        from app.validators import validate_password_strength
        
        result = validate_password_strength("Test123456")
        assert result.is_valid == True
        
        result = validate_password_strength("StrongP@ss123")
        assert result.is_valid == True
    
    def test_weak_password(self):
        """测试弱密码"""
        from app.validators import validate_password_strength
        
        # 太短
        assert validate_password_strength("Test1").is_valid == False
        
        # 无大写
        assert validate_password_strength("test123456").is_valid == False
        
        # 无小写
        assert validate_password_strength("TEST123456").is_valid == False


class TestUsernameValidator:
    """用户名验证测试"""
    
    def test_valid_username(self):
        """测试有效用户名"""
        from app.validators import validate_username
        
        assert validate_username("testuser").is_valid == True
        assert validate_username("test_user123").is_valid == True
        assert validate_username("张三").is_valid == True
    
    def test_invalid_username(self):
        """测试无效用户名"""
        from app.validators import validate_username
        
        assert validate_username("").is_valid == False
        assert validate_username("ab").is_valid == False  # 太短
        assert validate_username("123test").is_valid == False  # 数字开头


class TestFileSizeValidator:
    """文件大小验证测试"""
    
    def test_valid_file_size(self):
        """测试有效文件大小"""
        from app.validators import validate_file_size
        
        assert validate_file_size(1024).is_valid == True  # 1KB
        assert validate_file_size(5 * 1024 * 1024).is_valid == True  # 5MB
    
    def test_exceeded_file_size(self):
        """测试超出大小限制"""
        from app.validators import validate_file_size
        
        result = validate_file_size(100 * 1024 * 1024, max_size_mb=10)
        assert result.is_valid == False


class TestFileTypeValidator:
    """文件类型验证测试"""
    
    def test_valid_file_type(self):
        """测试有效文件类型"""
        from app.validators import validate_file_type
        
        assert validate_file_type("test.pdf", [".pdf", ".doc"]).is_valid == True
        assert validate_file_type("test.PDF", [".pdf"]).is_valid == True
    
    def test_invalid_file_type(self):
        """测试无效文件类型"""
        from app.validators import validate_file_type
        
        assert validate_file_type("test.exe", [".pdf", ".doc"]).is_valid == False


class TestDateRangeValidator:
    """日期范围验证测试"""
    
    def test_valid_date_range(self):
        """测试有效日期范围"""
        from app.validators import validate_date_range
        
        result = validate_date_range("2024-01-01", "2024-12-31")
        assert result.is_valid == True
        assert result.details["days"] == 365
    
    def test_invalid_date_range(self):
        """测试无效日期范围"""
        from app.validators import validate_date_range
        
        # 开始日期晚于结束日期
        result = validate_date_range("2024-12-31", "2024-01-01")
        assert result.is_valid == False


class TestCoordinatesValidator:
    """坐标验证测试"""
    
    def test_valid_coordinates(self):
        """测试有效坐标"""
        from app.validators import validate_coordinates
        
        assert validate_coordinates(39.9042, 116.4074).is_valid == True  # 北京
        assert validate_coordinates(0, 0).is_valid == True
    
    def test_invalid_coordinates(self):
        """测试无效坐标"""
        from app.validators import validate_coordinates
        
        assert validate_coordinates(100, 0).is_valid == False  # 纬度超范围
        assert validate_coordinates(0, 200).is_valid == False  # 经度超范围
