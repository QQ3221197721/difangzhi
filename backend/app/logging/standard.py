# 地方志数据智能管理系统 - 日志规范
"""统一日志配置和格式化"""

import logging
import sys
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import structlog


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogConfig:
    """日志配置"""
    level: LogLevel = LogLevel.INFO
    format: str = "json"  # json/console/text
    output: str = "stdout"  # stdout/file/both
    file_path: str = "logs/app.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    include_timestamp: bool = True
    include_level: bool = True
    include_logger_name: bool = True
    include_function_name: bool = True
    include_line_number: bool = False
    include_thread_name: bool = False
    include_process_id: bool = False
    # 敏感字段脱敏
    sensitive_fields: list = None
    # 额外字段
    extra_fields: Dict[str, Any] = None
    
    def __post_init__(self):
        self.sensitive_fields = self.sensitive_fields or [
            "password", "token", "secret", "api_key", "auth",
            "credit_card", "ssn", "id_card"
        ]
        self.extra_fields = self.extra_fields or {}


class LogFormatter:
    """日志格式化器"""
    
    # 日志格式规范
    LOG_SCHEMA = {
        "timestamp": "ISO8601格式时间戳",
        "level": "日志级别",
        "logger": "日志器名称",
        "message": "日志消息",
        "trace_id": "链路追踪ID",
        "span_id": "Span ID",
        "user_id": "用户ID",
        "request_id": "请求ID",
        "service": "服务名称",
        "environment": "运行环境",
        "extra": "额外字段"
    }
    
    def __init__(self, config: LogConfig):
        self.config = config
    
    def format_json(self, record: Dict[str, Any]) -> str:
        """JSON格式"""
        output = {}
        
        if self.config.include_timestamp:
            output["timestamp"] = record.get("timestamp", datetime.now().isoformat())
        
        if self.config.include_level:
            output["level"] = record.get("level", "INFO")
        
        if self.config.include_logger_name:
            output["logger"] = record.get("logger", "root")
        
        output["message"] = record.get("event", record.get("message", ""))
        
        # 追踪信息
        for key in ["trace_id", "span_id", "request_id", "user_id"]:
            if key in record:
                output[key] = record[key]
        
        # 服务信息
        output["service"] = self.config.extra_fields.get("service", "local-chronicles")
        output["environment"] = self.config.extra_fields.get("environment", "development")
        
        # 额外字段
        extra = {k: v for k, v in record.items() 
                 if k not in ["timestamp", "level", "logger", "event", "message",
                              "trace_id", "span_id", "request_id", "user_id"]}
        if extra:
            output["extra"] = extra
        
        # 敏感字段脱敏
        output = self._mask_sensitive(output)
        
        return json.dumps(output, ensure_ascii=False, default=str)
    
    def format_text(self, record: Dict[str, Any]) -> str:
        """文本格式"""
        parts = []
        
        if self.config.include_timestamp:
            parts.append(record.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        if self.config.include_level:
            level = record.get("level", "INFO")
            parts.append(f"[{level:8}]")
        
        if self.config.include_logger_name:
            parts.append(f"[{record.get('logger', 'root')}]")
        
        parts.append(record.get("event", record.get("message", "")))
        
        return " ".join(parts)
    
    def _mask_sensitive(self, data: Dict) -> Dict:
        """脱敏敏感字段"""
        def _mask_value(key: str, value: Any) -> Any:
            key_lower = key.lower()
            for sensitive in self.config.sensitive_fields:
                if sensitive in key_lower:
                    if isinstance(value, str):
                        if len(value) > 4:
                            return value[:2] + "*" * (len(value) - 4) + value[-2:]
                        return "*" * len(value)
                    return "***"
            return value
        
        def _process(obj):
            if isinstance(obj, dict):
                return {k: _mask_value(k, _process(v)) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_process(item) for item in obj]
            return obj
        
        return _process(data)


def setup_logging(config: LogConfig = None) -> None:
    """配置日志系统"""
    config = config or LogConfig()
    
    # structlog处理器
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # 标准库配置
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, config.level.value),
        handlers=_create_handlers(config)
    )
    
    # 降低第三方库日志级别
    for name in ["uvicorn", "uvicorn.access", "sqlalchemy", "httpx", "httpcore"]:
        logging.getLogger(name).setLevel(logging.WARNING)


def _create_handlers(config: LogConfig) -> list:
    """创建日志处理器"""
    handlers = []
    
    if config.output in ["stdout", "both"]:
        handlers.append(logging.StreamHandler(sys.stdout))
    
    if config.output in ["file", "both"]:
        from logging.handlers import RotatingFileHandler
        from pathlib import Path
        
        Path(config.file_path).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8"
        )
        handlers.append(file_handler)
    
    return handlers


def get_logger(name: str = None) -> structlog.BoundLogger:
    """获取日志实例"""
    return structlog.get_logger(name)


# 日志规范文档
LOG_STANDARD = """
# 日志规范

## 日志级别使用规范

- **DEBUG**: 调试信息，仅开发环境启用
- **INFO**: 常规业务流程记录
- **WARNING**: 潜在问题，但不影响正常运行
- **ERROR**: 错误，需要关注但系统仍可运行
- **CRITICAL**: 严重错误，系统无法正常运行

## 日志内容规范

1. **必须包含上下文**
   - trace_id: 分布式追踪ID
   - request_id: 请求ID
   - user_id: 用户ID(如适用)

2. **消息格式**
   - 使用英文或中文，保持一致
   - 动作 + 对象 + 结果
   - 示例: "用户登录成功", "文档创建失败"

3. **错误日志**
   - 包含错误类型
   - 包含错误消息
   - 包含堆栈信息(DEBUG级别)
   - 包含相关上下文

## 敏感信息处理

以下字段自动脱敏:
- password, token, secret
- api_key, auth
- credit_card, ssn, id_card

## 日志输出格式

### JSON格式(生产环境)
```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "app.api.documents",
  "message": "文档创建成功",
  "trace_id": "abc123",
  "request_id": "req-456",
  "user_id": 1,
  "service": "local-chronicles",
  "environment": "production",
  "extra": {
    "document_id": 100,
    "title": "北京志"
  }
}
```

### 文本格式(开发环境)
```
2024-01-01 12:00:00 [INFO    ] [app.api.documents] 文档创建成功 document_id=100
```
"""
