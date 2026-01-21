# 地方志数据智能管理系统 - 日志配置
"""结构化日志配置"""

import logging
import sys
from typing import Any, Dict
import structlog


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: str = None
):
    """
    配置结构化日志
    
    Args:
        level: 日志级别
        json_format: 是否输出JSON格式
        log_file: 日志文件路径
    """
    
    # 时间戳处理器
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    # 共享处理器
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        # JSON格式输出
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False)
        ]
    else:
        # 控制台友好格式
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # 配置标准库logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 文件日志
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)
    
    # 减少第三方库日志
    for logger_name in ["uvicorn", "sqlalchemy", "httpx", "urllib3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """获取logger实例"""
    return structlog.get_logger(name)


# 日志配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    },
    "loggers": {
        "uvicorn": {"level": "INFO"},
        "sqlalchemy": {"level": "WARNING"},
        "celery": {"level": "INFO"},
    }
}
