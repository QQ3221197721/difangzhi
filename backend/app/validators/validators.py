# 地方志数据智能管理系统 - 数据验证器
"""常用数据验证函数"""

import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional, Tuple, Union


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    message: str = ""
    details: Optional[dict] = None


def validate_email(email: str) -> ValidationResult:
    """
    验证邮箱格式
    
    Args:
        email: 邮箱地址
        
    Returns:
        验证结果
    """
    if not email:
        return ValidationResult(False, "邮箱不能为空")
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email):
        return ValidationResult(True, "邮箱格式正确")
    else:
        return ValidationResult(False, "邮箱格式不正确")


def validate_phone(phone: str, region: str = "CN") -> ValidationResult:
    """
    验证手机号格式
    
    Args:
        phone: 手机号
        region: 地区代码
        
    Returns:
        验证结果
    """
    if not phone:
        return ValidationResult(False, "手机号不能为空")
    
    # 中国大陆手机号
    if region == "CN":
        pattern = r'^1[3-9]\d{9}$'
        if re.match(pattern, phone):
            return ValidationResult(True, "手机号格式正确")
        else:
            return ValidationResult(False, "请输入正确的11位手机号")
    
    # 其他地区简单验证
    if len(phone) >= 7 and phone.isdigit():
        return ValidationResult(True, "手机号格式正确")
    
    return ValidationResult(False, "手机号格式不正确")


def validate_id_card(id_card: str) -> ValidationResult:
    """
    验证中国大陆身份证号
    
    Args:
        id_card: 身份证号
        
    Returns:
        验证结果（包含提取的信息）
    """
    if not id_card:
        return ValidationResult(False, "身份证号不能为空")
    
    id_card = id_card.upper()
    
    # 检查长度
    if len(id_card) != 18:
        return ValidationResult(False, "身份证号必须是18位")
    
    # 检查前17位是否为数字
    if not id_card[:17].isdigit():
        return ValidationResult(False, "身份证号格式不正确")
    
    # 检查最后一位
    if not (id_card[17].isdigit() or id_card[17] == 'X'):
        return ValidationResult(False, "身份证号最后一位格式不正确")
    
    # 加权因子
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    # 校验码对应值
    check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
    
    # 计算校验码
    total = sum(int(id_card[i]) * weights[i] for i in range(17))
    expected_check = check_codes[total % 11]
    
    if id_card[17] != expected_check:
        return ValidationResult(False, "身份证号校验码不正确")
    
    # 提取信息
    try:
        birth_year = int(id_card[6:10])
        birth_month = int(id_card[10:12])
        birth_day = int(id_card[12:14])
        birth_date = date(birth_year, birth_month, birth_day)
        
        # 验证日期有效性
        if birth_date > date.today():
            return ValidationResult(False, "出生日期不能是未来日期")
        
        gender = "男" if int(id_card[16]) % 2 == 1 else "女"
        
        return ValidationResult(
            True, 
            "身份证号验证通过",
            details={
                "birth_date": birth_date.isoformat(),
                "gender": gender,
                "region_code": id_card[:6]
            }
        )
    except ValueError:
        return ValidationResult(False, "身份证号中的出生日期无效")


def validate_password_strength(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digit: bool = True,
    require_special: bool = False
) -> ValidationResult:
    """
    验证密码强度
    
    Args:
        password: 密码
        min_length: 最小长度
        require_uppercase: 是否需要大写字母
        require_lowercase: 是否需要小写字母
        require_digit: 是否需要数字
        require_special: 是否需要特殊字符
        
    Returns:
        验证结果
    """
    if not password:
        return ValidationResult(False, "密码不能为空")
    
    errors = []
    
    if len(password) < min_length:
        errors.append(f"密码长度至少{min_length}位")
    
    if require_uppercase and not re.search(r'[A-Z]', password):
        errors.append("密码需包含大写字母")
    
    if require_lowercase and not re.search(r'[a-z]', password):
        errors.append("密码需包含小写字母")
    
    if require_digit and not re.search(r'\d', password):
        errors.append("密码需包含数字")
    
    if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("密码需包含特殊字符")
    
    if errors:
        return ValidationResult(False, "；".join(errors))
    
    # 计算密码强度
    strength = 0
    if len(password) >= 8:
        strength += 1
    if len(password) >= 12:
        strength += 1
    if re.search(r'[A-Z]', password):
        strength += 1
    if re.search(r'[a-z]', password):
        strength += 1
    if re.search(r'\d', password):
        strength += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        strength += 1
    
    strength_text = ["弱", "弱", "中", "中", "强", "强", "很强"][min(strength, 6)]
    
    return ValidationResult(
        True, 
        f"密码强度: {strength_text}",
        details={"strength": strength, "strength_text": strength_text}
    )


def validate_username(
    username: str,
    min_length: int = 3,
    max_length: int = 20
) -> ValidationResult:
    """
    验证用户名
    
    Args:
        username: 用户名
        min_length: 最小长度
        max_length: 最大长度
        
    Returns:
        验证结果
    """
    if not username:
        return ValidationResult(False, "用户名不能为空")
    
    if len(username) < min_length:
        return ValidationResult(False, f"用户名长度至少{min_length}位")
    
    if len(username) > max_length:
        return ValidationResult(False, f"用户名长度不能超过{max_length}位")
    
    # 只允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fa5]+$', username):
        return ValidationResult(False, "用户名只能包含字母、数字、下划线和中文")
    
    # 不能以数字开头
    if username[0].isdigit():
        return ValidationResult(False, "用户名不能以数字开头")
    
    return ValidationResult(True, "用户名格式正确")


def validate_file_size(
    size_bytes: int,
    max_size_mb: float = 10
) -> ValidationResult:
    """
    验证文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        max_size_mb: 最大大小（MB）
        
    Returns:
        验证结果
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if size_bytes <= 0:
        return ValidationResult(False, "文件大小无效")
    
    if size_bytes > max_size_bytes:
        actual_mb = size_bytes / 1024 / 1024
        return ValidationResult(
            False, 
            f"文件大小超出限制，当前{actual_mb:.1f}MB，最大允许{max_size_mb}MB"
        )
    
    return ValidationResult(True, "文件大小符合要求")


def validate_file_type(
    filename: str,
    allowed_extensions: List[str]
) -> ValidationResult:
    """
    验证文件类型
    
    Args:
        filename: 文件名
        allowed_extensions: 允许的扩展名列表
        
    Returns:
        验证结果
    """
    if not filename:
        return ValidationResult(False, "文件名不能为空")
    
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    if not ext:
        return ValidationResult(False, "无法识别文件类型")
    
    allowed = [e.lower().lstrip('.') for e in allowed_extensions]
    
    if ext not in allowed:
        return ValidationResult(
            False, 
            f"不支持的文件类型: .{ext}，允许的类型: {', '.join(allowed)}"
        )
    
    return ValidationResult(True, "文件类型符合要求")


def validate_date_range(
    start_date: Union[str, date, datetime],
    end_date: Union[str, date, datetime]
) -> ValidationResult:
    """
    验证日期范围
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        验证结果
    """
    def parse_date(d) -> Optional[date]:
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, date):
            return d
        if isinstance(d, str):
            try:
                return datetime.strptime(d, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None
    
    start = parse_date(start_date)
    end = parse_date(end_date)
    
    if start is None:
        return ValidationResult(False, "开始日期格式不正确")
    
    if end is None:
        return ValidationResult(False, "结束日期格式不正确")
    
    if start > end:
        return ValidationResult(False, "开始日期不能晚于结束日期")
    
    days_diff = (end - start).days
    
    return ValidationResult(
        True, 
        "日期范围有效",
        details={"days": days_diff}
    )


def validate_coordinates(
    latitude: float,
    longitude: float
) -> ValidationResult:
    """
    验证经纬度坐标
    
    Args:
        latitude: 纬度
        longitude: 经度
        
    Returns:
        验证结果
    """
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return ValidationResult(False, "坐标必须是数字")
    
    if not -90 <= latitude <= 90:
        return ValidationResult(False, "纬度必须在-90到90之间")
    
    if not -180 <= longitude <= 180:
        return ValidationResult(False, "经度必须在-180到180之间")
    
    return ValidationResult(True, "坐标有效")


def validate_url(url: str) -> ValidationResult:
    """
    验证URL格式
    
    Args:
        url: URL地址
        
    Returns:
        验证结果
    """
    if not url:
        return ValidationResult(False, "URL不能为空")
    
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    
    if re.match(pattern, url, re.IGNORECASE):
        return ValidationResult(True, "URL格式正确")
    else:
        return ValidationResult(False, "URL格式不正确")


def validate_chinese_name(name: str) -> ValidationResult:
    """
    验证中文姓名
    
    Args:
        name: 姓名
        
    Returns:
        验证结果
    """
    if not name:
        return ValidationResult(False, "姓名不能为空")
    
    if len(name) < 2:
        return ValidationResult(False, "姓名至少2个字")
    
    if len(name) > 20:
        return ValidationResult(False, "姓名不能超过20个字")
    
    # 只允许中文和少数民族名字中的点
    if not re.match(r'^[\u4e00-\u9fa5·]+$', name):
        return ValidationResult(False, "姓名只能包含中文字符")
    
    return ValidationResult(True, "姓名格式正确")
