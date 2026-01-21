# 地方志数据智能管理系统 - 日志处理器
"""自定义日志处理器"""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from queue import Queue
from threading import Thread
import structlog


class JsonFileHandler(logging.FileHandler):
    """JSON格式文件处理器"""
    
    def __init__(
        self,
        filename: str,
        mode: str = "a",
        encoding: str = "utf-8",
        **kwargs
    ):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename, mode, encoding, **kwargs)
    
    def emit(self, record: logging.LogRecord):
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # 添加额外字段
            if hasattr(record, "trace_id"):
                log_entry["trace_id"] = record.trace_id
            if hasattr(record, "request_id"):
                log_entry["request_id"] = record.request_id
            if hasattr(record, "user_id"):
                log_entry["user_id"] = record.user_id
            
            # 添加异常信息
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            
            self.stream.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            self.flush()
        except Exception:
            self.handleError(record)


class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""
    
    def __init__(self, handler: logging.Handler, queue_size: int = 10000):
        super().__init__()
        self.handler = handler
        self.queue: Queue = Queue(maxsize=queue_size)
        self._running = True
        self._worker = Thread(target=self._process_logs, daemon=True)
        self._worker.start()
    
    def emit(self, record: logging.LogRecord):
        try:
            self.queue.put_nowait(record)
        except Exception:
            self.handleError(record)
    
    def _process_logs(self):
        while self._running or not self.queue.empty():
            try:
                record = self.queue.get(timeout=1.0)
                self.handler.emit(record)
            except Exception:
                pass
    
    def close(self):
        self._running = False
        self._worker.join(timeout=5.0)
        self.handler.close()
        super().close()


class ElasticsearchHandler(logging.Handler):
    """Elasticsearch日志处理器"""
    
    def __init__(
        self,
        hosts: List[str],
        index_prefix: str = "logs",
        batch_size: int = 100,
        flush_interval: float = 5.0
    ):
        super().__init__()
        self.hosts = hosts
        self.index_prefix = index_prefix
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer: List[Dict] = []
        self._client = None
        self._last_flush = datetime.now()
    
    def _get_client(self):
        if self._client is None:
            try:
                from elasticsearch import Elasticsearch
                self._client = Elasticsearch(self.hosts)
            except ImportError:
                structlog.get_logger().warning("elasticsearch包未安装")
        return self._client
    
    def _get_index_name(self) -> str:
        return f"{self.index_prefix}-{datetime.now().strftime('%Y.%m.%d')}"
    
    def emit(self, record: logging.LogRecord):
        try:
            log_entry = {
                "@timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # 添加上下文字段
            for attr in ["trace_id", "request_id", "user_id", "service", "environment"]:
                if hasattr(record, attr):
                    log_entry[attr] = getattr(record, attr)
            
            # 异常信息
            if record.exc_info:
                log_entry["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "stacktrace": self.formatException(record.exc_info)
                }
            
            self.buffer.append(log_entry)
            
            # 检查是否需要刷新
            if len(self.buffer) >= self.batch_size:
                self._flush()
            elif (datetime.now() - self._last_flush).total_seconds() > self.flush_interval:
                self._flush()
                
        except Exception:
            self.handleError(record)
    
    def _flush(self):
        if not self.buffer:
            return
        
        client = self._get_client()
        if not client:
            self.buffer.clear()
            return
        
        try:
            index_name = self._get_index_name()
            actions = []
            for doc in self.buffer:
                actions.append({"index": {"_index": index_name}})
                actions.append(doc)
            
            if actions:
                client.bulk(body=actions, refresh=False)
            
            self.buffer.clear()
            self._last_flush = datetime.now()
        except Exception as e:
            structlog.get_logger().error("ES日志写入失败", error=str(e))
    
    def close(self):
        self._flush()
        if self._client:
            self._client.close()
        super().close()


class RotatingJsonFileHandler(logging.Handler):
    """按日期轮转的JSON文件处理器"""
    
    def __init__(
        self,
        log_dir: str = "logs",
        prefix: str = "app",
        max_bytes: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 30
    ):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.prefix = prefix
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._current_date = None
        self._current_handler = None
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_handler(self) -> logging.FileHandler:
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self._current_date != today:
            if self._current_handler:
                self._current_handler.close()
            
            log_file = self.log_dir / f"{self.prefix}-{today}.json"
            self._current_handler = logging.FileHandler(
                log_file, encoding="utf-8"
            )
            self._current_date = today
            
            # 清理旧日志
            self._cleanup_old_logs()
        
        return self._current_handler
    
    def _cleanup_old_logs(self):
        """清理旧日志文件"""
        import os
        
        log_files = sorted(
            self.log_dir.glob(f"{self.prefix}-*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        for old_file in log_files[self.backup_count:]:
            try:
                old_file.unlink()
            except Exception:
                pass
    
    def emit(self, record: logging.LogRecord):
        try:
            handler = self._get_handler()
            
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            
            handler.stream.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            handler.flush()
        except Exception:
            self.handleError(record)
    
    def close(self):
        if self._current_handler:
            self._current_handler.close()
        super().close()
