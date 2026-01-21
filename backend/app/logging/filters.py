# 地方志数据智能管理系统 - 日志过滤器
"""敏感数据脱敏、速率限制等过滤器"""

import logging
import re
import time
from collections import defaultdict
from typing import Dict, List, Pattern, Set
import structlog


class SensitiveDataFilter(logging.Filter):
    """敏感数据脱敏过滤器"""
    
    # 默认敏感字段模式
    DEFAULT_PATTERNS = {
        "password": r'"password"\s*:\s*"[^"]*"',
        "token": r'"(access_token|refresh_token|api_token|token)"\s*:\s*"[^"]*"',
        "api_key": r'"(api_key|apikey|api-key)"\s*:\s*"[^"]*"',
        "secret": r'"(secret|secret_key)"\s*:\s*"[^"]*"',
        "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b1[3-9]\d{9}\b',
        "id_card": r'\b\d{17}[\dXx]\b',
        "ip_address": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    }
    
    def __init__(
        self,
        patterns: Dict[str, str] = None,
        mask_char: str = "*",
        preserve_length: bool = True
    ):
        super().__init__()
        self.patterns: Dict[str, Pattern] = {}
        self.mask_char = mask_char
        self.preserve_length = preserve_length
        
        # 编译正则表达式
        all_patterns = {**self.DEFAULT_PATTERNS, **(patterns or {})}
        for name, pattern in all_patterns.items():
            self.patterns[name] = re.compile(pattern, re.IGNORECASE)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤并脱敏日志记录"""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._mask_message(record.msg)
        
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._mask_message(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def _mask_message(self, message: str) -> str:
        """脱敏消息"""
        for name, pattern in self.patterns.items():
            message = pattern.sub(self._create_mask(name), message)
        return message
    
    def _create_mask(self, field_name: str):
        """创建脱敏替换函数"""
        def replacer(match):
            original = match.group(0)
            if self.preserve_length:
                # 保留首尾字符
                if len(original) > 4:
                    return original[:2] + self.mask_char * (len(original) - 4) + original[-2:]
                return self.mask_char * len(original)
            return f"[{field_name.upper()}_MASKED]"
        return replacer
    
    def add_pattern(self, name: str, pattern: str):
        """添加自定义脱敏模式"""
        self.patterns[name] = re.compile(pattern, re.IGNORECASE)


class RateLimitFilter(logging.Filter):
    """日志速率限制过滤器"""
    
    def __init__(
        self,
        rate_limit: int = 100,  # 每个周期最大日志数
        period: float = 1.0,     # 周期（秒）
        burst: int = 10          # 突发容量
    ):
        super().__init__()
        self.rate_limit = rate_limit
        self.period = period
        self.burst = burst
        
        # 每个日志器的计数器
        self._counters: Dict[str, List[float]] = defaultdict(list)
        self._dropped: Dict[str, int] = defaultdict(int)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """速率限制过滤"""
        now = time.time()
        key = f"{record.name}:{record.levelno}"
        
        # 清理过期时间戳
        self._counters[key] = [
            ts for ts in self._counters[key]
            if now - ts < self.period
        ]
        
        # 检查是否超过速率限制
        if len(self._counters[key]) >= self.rate_limit:
            self._dropped[key] += 1
            
            # 定期输出丢弃统计
            if self._dropped[key] % 100 == 0:
                structlog.get_logger().warning(
                    "日志速率限制",
                    logger=record.name,
                    level=record.levelname,
                    dropped_count=self._dropped[key]
                )
            return False
        
        self._counters[key].append(now)
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """获取丢弃统计"""
        return dict(self._dropped)


class DuplicateFilter(logging.Filter):
    """重复日志过滤器"""
    
    def __init__(self, suppress_time: float = 5.0):
        super().__init__()
        self.suppress_time = suppress_time
        self._recent: Dict[str, float] = {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤重复日志"""
        now = time.time()
        
        # 生成消息指纹
        msg_key = f"{record.name}:{record.levelno}:{record.getMessage()}"
        
        # 检查是否为重复消息
        if msg_key in self._recent:
            last_time = self._recent[msg_key]
            if now - last_time < self.suppress_time:
                return False
        
        self._recent[msg_key] = now
        
        # 清理旧记录
        self._cleanup(now)
        
        return True
    
    def _cleanup(self, now: float):
        """清理过期记录"""
        expired_keys = [
            key for key, ts in self._recent.items()
            if now - ts > self.suppress_time * 2
        ]
        for key in expired_keys:
            del self._recent[key]


class LevelFilter(logging.Filter):
    """按级别过滤"""
    
    def __init__(
        self,
        min_level: int = logging.DEBUG,
        max_level: int = logging.CRITICAL,
        exclude_levels: Set[int] = None
    ):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level
        self.exclude_levels = exclude_levels or set()
    
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno in self.exclude_levels:
            return False
        return self.min_level <= record.levelno <= self.max_level


class ContextFilter(logging.Filter):
    """上下文注入过滤器"""
    
    def __init__(self, extra_fields: Dict[str, str] = None):
        super().__init__()
        self.extra_fields = extra_fields or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """注入额外字段"""
        for key, value in self.extra_fields.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        
        # 从contextvars获取追踪信息
        from .context import _trace_id, _request_id, _user_id
        
        if not hasattr(record, 'trace_id'):
            record.trace_id = _trace_id.get()
        if not hasattr(record, 'request_id'):
            record.request_id = _request_id.get()
        if not hasattr(record, 'user_id'):
            record.user_id = _user_id.get()
        
        return True
