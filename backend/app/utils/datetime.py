# 地方志数据智能管理系统 - 日期时间工具
"""日期时间处理、格式化、转换等工具"""

import re
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, Union, List
from zoneinfo import ZoneInfo


# 默认时区
DEFAULT_TIMEZONE = ZoneInfo("Asia/Shanghai")

# 日期格式
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y年%m月%d日",
    "%Y.%m.%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m",
    "%Y/%m",
    "%Y年%m月",
    "%Y",
]

DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y年%m月%d日 %H:%M:%S",
]


def format_datetime(
    dt: Optional[datetime],
    format_str: str = "%Y-%m-%d %H:%M:%S",
    default: str = ""
) -> str:
    """
    格式化日期时间
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串
        default: 默认值
        
    Returns:
        格式化后的字符串
    """
    if dt is None:
        return default
    
    return dt.strftime(format_str)


def parse_datetime(
    date_str: str,
    formats: Optional[List[str]] = None
) -> Optional[datetime]:
    """
    解析日期时间字符串
    
    Args:
        date_str: 日期时间字符串
        formats: 尝试的格式列表
        
    Returns:
        日期时间对象或None
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    if formats is None:
        formats = DATETIME_FORMATS + DATE_FORMATS
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def get_date_range(
    range_type: str,
    reference_date: Optional[datetime] = None
) -> Tuple[datetime, datetime]:
    """
    获取日期范围
    
    Args:
        range_type: 范围类型 (today/yesterday/this_week/last_week/this_month/last_month/this_year)
        reference_date: 参考日期
        
    Returns:
        (开始日期, 结束日期)
    """
    if reference_date is None:
        reference_date = datetime.now(DEFAULT_TIMEZONE)
    
    today = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if range_type == "today":
        start = today
        end = today + timedelta(days=1) - timedelta(seconds=1)
    
    elif range_type == "yesterday":
        start = today - timedelta(days=1)
        end = today - timedelta(seconds=1)
    
    elif range_type == "this_week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7) - timedelta(seconds=1)
    
    elif range_type == "last_week":
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=7) - timedelta(seconds=1)
    
    elif range_type == "this_month":
        start = today.replace(day=1)
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(seconds=1)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(seconds=1)
    
    elif range_type == "last_month":
        if today.month == 1:
            start = today.replace(year=today.year - 1, month=12, day=1)
        else:
            start = today.replace(month=today.month - 1, day=1)
        end = today.replace(day=1) - timedelta(seconds=1)
    
    elif range_type == "this_year":
        start = today.replace(month=1, day=1)
        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(seconds=1)
    
    else:
        start = today
        end = today + timedelta(days=1) - timedelta(seconds=1)
    
    return start, end


def time_ago(dt: datetime, now: Optional[datetime] = None) -> str:
    """
    计算相对时间（多久之前）
    
    Args:
        dt: 目标时间
        now: 当前时间
        
    Returns:
        相对时间描述
    """
    if now is None:
        now = datetime.now(DEFAULT_TIMEZONE)
    
    # 确保时区一致
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TIMEZONE)
    if now.tzinfo is None:
        now = now.replace(tzinfo=DEFAULT_TIMEZONE)
    
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "未来"
    elif seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}分钟前"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}小时前"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days}天前"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks}周前"
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f"{months}月前"
    else:
        years = int(seconds / 31536000)
        return f"{years}年前"


def is_valid_date(date_str: str) -> bool:
    """
    检查日期字符串是否有效
    
    Args:
        date_str: 日期字符串
        
    Returns:
        是否有效
    """
    return parse_datetime(date_str) is not None


def get_current_timestamp() -> int:
    """
    获取当前时间戳（毫秒）
    
    Returns:
        时间戳
    """
    return int(datetime.now().timestamp() * 1000)


def timestamp_to_datetime(timestamp: int) -> datetime:
    """
    时间戳转日期时间
    
    Args:
        timestamp: 时间戳（毫秒或秒）
        
    Returns:
        日期时间对象
    """
    # 判断是毫秒还是秒
    if timestamp > 10000000000:
        timestamp = timestamp / 1000
    
    return datetime.fromtimestamp(timestamp, tz=DEFAULT_TIMEZONE)


def get_age(birth_date: date) -> int:
    """
    计算年龄
    
    Args:
        birth_date: 出生日期
        
    Returns:
        年龄
    """
    today = date.today()
    age = today.year - birth_date.year
    
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    
    return age


def get_quarter(dt: Optional[datetime] = None) -> int:
    """
    获取季度
    
    Args:
        dt: 日期时间
        
    Returns:
        季度 (1-4)
    """
    if dt is None:
        dt = datetime.now()
    
    return (dt.month - 1) // 3 + 1


def get_week_of_year(dt: Optional[datetime] = None) -> int:
    """
    获取一年中的第几周
    
    Args:
        dt: 日期时间
        
    Returns:
        周数
    """
    if dt is None:
        dt = datetime.now()
    
    return dt.isocalendar()[1]


def date_range_iterator(
    start_date: date,
    end_date: date,
    step_days: int = 1
):
    """
    日期范围迭代器
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        step_days: 步长（天数）
        
    Yields:
        日期
    """
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=step_days)
