"""
健康检查增强 - 深度检查、依赖探测、自动恢复、就绪/存活探针
Health Check Enhancement - Deep Check, Dependency Probe, Auto Recovery
"""

import asyncio
import socket
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import logging
import platform
import psutil

logger = logging.getLogger(__name__)


# ==================== 健康状态 ====================

class HealthStatus(str, Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """检查类型"""
    LIVENESS = "liveness"    # 存活检查
    READINESS = "readiness"  # 就绪检查
    STARTUP = "startup"      # 启动检查


@dataclass
class CheckResult:
    """检查结果"""
    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class HealthReport:
    """健康报告"""
    status: HealthStatus
    checks: List[CheckResult]
    uptime_seconds: float
    version: str = "1.0.0"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "uptime_seconds": round(self.uptime_seconds, 2),
            "version": self.version,
            "timestamp": self.timestamp.isoformat()
        }


# ==================== 健康检查器 ====================

class HealthChecker(ABC):
    """健康检查器基类"""
    
    def __init__(
        self,
        name: str,
        check_type: CheckType = CheckType.READINESS,
        timeout: float = 5.0,
        critical: bool = True
    ):
        self.name = name
        self.check_type = check_type
        self.timeout = timeout
        self.critical = critical
    
    @abstractmethod
    async def check(self) -> CheckResult:
        """执行检查"""
        pass
    
    async def execute(self) -> CheckResult:
        """执行检查(带超时)"""
        start = time.perf_counter()
        
        try:
            result = await asyncio.wait_for(
                self.check(),
                timeout=self.timeout
            )
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except asyncio.TimeoutError:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"检查超时 ({self.timeout}s)",
                duration_ms=(time.perf_counter() - start) * 1000
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000
            )


# ==================== 内置检查器 ====================

class DatabaseChecker(HealthChecker):
    """数据库健康检查"""
    
    def __init__(
        self,
        session_factory: Callable,
        query: str = "SELECT 1",
        **kwargs
    ):
        super().__init__("database", **kwargs)
        self.session_factory = session_factory
        self.query = query
    
    async def check(self) -> CheckResult:
        try:
            async with self.session_factory() as session:
                from sqlalchemy import text
                result = await session.execute(text(self.query))
                result.fetchone()
            
            return CheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="数据库连接正常"
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"数据库连接失败: {e}"
            )


class RedisChecker(HealthChecker):
    """Redis健康检查"""
    
    def __init__(self, redis_client: Any, **kwargs):
        super().__init__("redis", **kwargs)
        self.redis = redis_client
    
    async def check(self) -> CheckResult:
        try:
            pong = await self.redis.ping()
            info = await self.redis.info("server")
            
            return CheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Redis连接正常",
                details={
                    "version": info.get("redis_version", "unknown"),
                    "uptime_days": info.get("uptime_in_days", 0)
                }
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis连接失败: {e}"
            )


class HTTPChecker(HealthChecker):
    """HTTP服务健康检查"""
    
    def __init__(
        self,
        url: str,
        expected_status: int = 200,
        **kwargs
    ):
        super().__init__(f"http:{url}", **kwargs)
        self.url = url
        self.expected_status = expected_status
    
    async def check(self) -> CheckResult:
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, timeout=self.timeout) as response:
                    if response.status == self.expected_status:
                        return CheckResult(
                            name=self.name,
                            status=HealthStatus.HEALTHY,
                            message=f"HTTP {response.status}",
                            details={"url": self.url, "status": response.status}
                        )
                    else:
                        return CheckResult(
                            name=self.name,
                            status=HealthStatus.DEGRADED,
                            message=f"期望 {self.expected_status}, 实际 {response.status}",
                            details={"url": self.url, "status": response.status}
                        )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP请求失败: {e}"
            )


class TCPChecker(HealthChecker):
    """TCP端口健康检查"""
    
    def __init__(self, host: str, port: int, **kwargs):
        super().__init__(f"tcp:{host}:{port}", **kwargs)
        self.host = host
        self.port = port
    
    async def check(self) -> CheckResult:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )
            writer.close()
            await writer.wait_closed()
            
            return CheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"{self.host}:{self.port} 可达",
                details={"host": self.host, "port": self.port}
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"TCP连接失败: {e}"
            )


class DiskChecker(HealthChecker):
    """磁盘空间健康检查"""
    
    def __init__(
        self,
        path: str = "/",
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
        **kwargs
    ):
        super().__init__("disk", **kwargs)
        self.path = path
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    async def check(self) -> CheckResult:
        try:
            usage = psutil.disk_usage(self.path)
            percent = usage.percent
            
            if percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"磁盘使用率严重: {percent}%"
            elif percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"磁盘使用率较高: {percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"磁盘使用率正常: {percent}%"
            
            return CheckResult(
                name=self.name,
                status=status,
                message=message,
                details={
                    "path": self.path,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": percent
                }
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"检查磁盘失败: {e}"
            )


class MemoryChecker(HealthChecker):
    """内存健康检查"""
    
    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
        **kwargs
    ):
        super().__init__("memory", **kwargs)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    async def check(self) -> CheckResult:
        try:
            memory = psutil.virtual_memory()
            percent = memory.percent
            
            if percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"内存使用率严重: {percent}%"
            elif percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"内存使用率较高: {percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"内存使用率正常: {percent}%"
            
            return CheckResult(
                name=self.name,
                status=status,
                message=message,
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": percent
                }
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"检查内存失败: {e}"
            )


class CPUChecker(HealthChecker):
    """CPU健康检查"""
    
    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 95.0,
        **kwargs
    ):
        super().__init__("cpu", **kwargs)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    async def check(self) -> CheckResult:
        try:
            # 获取1秒内的CPU使用率
            percent = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            
            if percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"CPU使用率严重: {percent}%"
            elif percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"CPU使用率较高: {percent}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU使用率正常: {percent}%"
            
            return CheckResult(
                name=self.name,
                status=status,
                message=message,
                details={
                    "percent": percent,
                    "cores": psutil.cpu_count(),
                    "load_1m": round(load_avg[0], 2),
                    "load_5m": round(load_avg[1], 2),
                    "load_15m": round(load_avg[2], 2)
                }
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message=f"检查CPU失败: {e}"
            )


class CustomChecker(HealthChecker):
    """自定义健康检查"""
    
    def __init__(
        self,
        name: str,
        check_func: Callable[[], Tuple[bool, str, Dict]],
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.check_func = check_func
    
    async def check(self) -> CheckResult:
        try:
            if asyncio.iscoroutinefunction(self.check_func):
                healthy, message, details = await self.check_func()
            else:
                healthy, message, details = self.check_func()
            
            return CheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
                message=message,
                details=details
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )


# ==================== 自动恢复 ====================

@dataclass
class RecoveryAction:
    """恢复动作"""
    name: str
    checker_name: str
    action: Callable[[], Any]
    max_retries: int = 3
    retry_interval: float = 10.0
    cooldown: float = 60.0
    
    _retry_count: int = field(default=0, init=False)
    _last_triggered: Optional[datetime] = field(default=None, init=False)


class AutoRecovery:
    """自动恢复管理器"""
    
    def __init__(self):
        self._actions: Dict[str, RecoveryAction] = {}
        self._history: List[Dict] = []
        self._max_history = 100
    
    def register(self, action: RecoveryAction):
        """注册恢复动作"""
        self._actions[action.checker_name] = action
        logger.info(f"注册恢复动作: {action.name} -> {action.checker_name}")
    
    async def try_recover(self, check_result: CheckResult) -> bool:
        """尝试恢复"""
        if check_result.status == HealthStatus.HEALTHY:
            return True
        
        action = self._actions.get(check_result.name)
        if not action:
            return False
        
        # 检查冷却
        if action._last_triggered:
            elapsed = (datetime.now() - action._last_triggered).total_seconds()
            if elapsed < action.cooldown:
                logger.debug(f"恢复动作 {action.name} 冷却中")
                return False
        
        # 检查重试次数
        if action._retry_count >= action.max_retries:
            logger.warning(f"恢复动作 {action.name} 已达最大重试次数")
            return False
        
        # 执行恢复
        try:
            logger.info(f"执行恢复动作: {action.name}")
            
            if asyncio.iscoroutinefunction(action.action):
                await action.action()
            else:
                action.action()
            
            action._retry_count += 1
            action._last_triggered = datetime.now()
            
            self._record_recovery(action, True)
            return True
            
        except Exception as e:
            logger.error(f"恢复动作失败: {action.name}, 错误: {e}")
            action._retry_count += 1
            self._record_recovery(action, False, str(e))
            return False
    
    def reset_retries(self, checker_name: str):
        """重置重试计数"""
        if checker_name in self._actions:
            self._actions[checker_name]._retry_count = 0
    
    def _record_recovery(
        self,
        action: RecoveryAction,
        success: bool,
        error: str = None
    ):
        """记录恢复历史"""
        self._history.append({
            "action": action.name,
            "checker": action.checker_name,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history//2:]
    
    def get_history(self) -> List[Dict]:
        """获取恢复历史"""
        return self._history.copy()


# ==================== 健康检查管理器 ====================

class HealthManager:
    """健康检查管理器"""
    
    def __init__(self):
        self._checkers: Dict[CheckType, List[HealthChecker]] = {
            CheckType.LIVENESS: [],
            CheckType.READINESS: [],
            CheckType.STARTUP: []
        }
        self._auto_recovery = AutoRecovery()
        self._start_time = datetime.now()
        self._version = "1.0.0"
        self._last_results: Dict[str, CheckResult] = {}
        self._check_interval = 30
        self._check_task: Optional[asyncio.Task] = None
    
    def register(self, checker: HealthChecker):
        """注册检查器"""
        self._checkers[checker.check_type].append(checker)
        logger.info(f"注册健康检查: {checker.name} ({checker.check_type.value})")
    
    def register_recovery(self, action: RecoveryAction):
        """注册恢复动作"""
        self._auto_recovery.register(action)
    
    async def check_liveness(self) -> HealthReport:
        """存活检查"""
        return await self._run_checks(CheckType.LIVENESS)
    
    async def check_readiness(self) -> HealthReport:
        """就绪检查"""
        return await self._run_checks(CheckType.READINESS)
    
    async def check_startup(self) -> HealthReport:
        """启动检查"""
        return await self._run_checks(CheckType.STARTUP)
    
    async def check_all(self) -> HealthReport:
        """完整健康检查"""
        all_checkers = (
            self._checkers[CheckType.LIVENESS] +
            self._checkers[CheckType.READINESS]
        )
        
        results = await asyncio.gather(
            *[checker.execute() for checker in all_checkers],
            return_exceptions=True
        )
        
        check_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_results.append(CheckResult(
                    name=all_checkers[i].name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(result)
                ))
            else:
                check_results.append(result)
        
        # 尝试自动恢复
        for result in check_results:
            if result.status != HealthStatus.HEALTHY:
                await self._auto_recovery.try_recover(result)
            else:
                self._auto_recovery.reset_retries(result.name)
        
        # 存储结果
        for result in check_results:
            self._last_results[result.name] = result
        
        overall_status = self._determine_status(check_results, all_checkers)
        
        return HealthReport(
            status=overall_status,
            checks=check_results,
            uptime_seconds=(datetime.now() - self._start_time).total_seconds(),
            version=self._version
        )
    
    async def _run_checks(self, check_type: CheckType) -> HealthReport:
        """运行指定类型的检查"""
        checkers = self._checkers[check_type]
        
        if not checkers:
            return HealthReport(
                status=HealthStatus.HEALTHY,
                checks=[],
                uptime_seconds=(datetime.now() - self._start_time).total_seconds(),
                version=self._version
            )
        
        results = await asyncio.gather(
            *[checker.execute() for checker in checkers],
            return_exceptions=True
        )
        
        check_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                check_results.append(CheckResult(
                    name=checkers[i].name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(result)
                ))
            else:
                check_results.append(result)
        
        overall_status = self._determine_status(check_results, checkers)
        
        return HealthReport(
            status=overall_status,
            checks=check_results,
            uptime_seconds=(datetime.now() - self._start_time).total_seconds(),
            version=self._version
        )
    
    def _determine_status(
        self,
        results: List[CheckResult],
        checkers: List[HealthChecker]
    ) -> HealthStatus:
        """确定整体状态"""
        has_unhealthy = False
        has_degraded = False
        
        for result, checker in zip(results, checkers):
            if result.status == HealthStatus.UNHEALTHY:
                if checker.critical:
                    return HealthStatus.UNHEALTHY
                has_unhealthy = True
            elif result.status == HealthStatus.DEGRADED:
                has_degraded = True
        
        if has_unhealthy or has_degraded:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    async def start_background_checks(self, interval: int = 30):
        """启动后台检查"""
        self._check_interval = interval
        
        async def check_loop():
            while True:
                await asyncio.sleep(self._check_interval)
                try:
                    await self.check_all()
                except Exception as e:
                    logger.error(f"后台健康检查失败: {e}")
        
        self._check_task = asyncio.create_task(check_loop())
        logger.info(f"后台健康检查已启动, 间隔: {interval}s")
    
    async def stop_background_checks(self):
        """停止后台检查"""
        if self._check_task:
            self._check_task.cancel()
            self._check_task = None
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds()
        }
    
    def get_last_results(self) -> Dict[str, Dict]:
        """获取最近检查结果"""
        return {
            name: result.to_dict()
            for name, result in self._last_results.items()
        }


# ==================== FastAPI集成 ====================

def create_health_routes(health_manager: HealthManager):
    """创建健康检查路由"""
    from fastapi import APIRouter, Response
    
    router = APIRouter(tags=["Health"])
    
    @router.get("/health")
    async def health():
        """完整健康检查"""
        report = await health_manager.check_all()
        status_code = 200 if report.status == HealthStatus.HEALTHY else 503
        return Response(
            content=json.dumps(report.to_dict()),
            status_code=status_code,
            media_type="application/json"
        )
    
    @router.get("/health/live")
    async def liveness():
        """存活检查(K8s liveness probe)"""
        report = await health_manager.check_liveness()
        status_code = 200 if report.status != HealthStatus.UNHEALTHY else 503
        return Response(
            content=json.dumps(report.to_dict()),
            status_code=status_code,
            media_type="application/json"
        )
    
    @router.get("/health/ready")
    async def readiness():
        """就绪检查(K8s readiness probe)"""
        report = await health_manager.check_readiness()
        status_code = 200 if report.status == HealthStatus.HEALTHY else 503
        return Response(
            content=json.dumps(report.to_dict()),
            status_code=status_code,
            media_type="application/json"
        )
    
    @router.get("/health/info")
    async def info():
        """系统信息"""
        return health_manager.get_system_info()
    
    return router


# 需要导入json
import json


# ==================== 全局实例 ====================

health_manager = HealthManager()


# ==================== 导出 ====================

__all__ = [
    # 状态枚举
    "HealthStatus",
    "CheckType",
    # 数据类
    "CheckResult",
    "HealthReport",
    "RecoveryAction",
    # 检查器
    "HealthChecker",
    "DatabaseChecker",
    "RedisChecker",
    "HTTPChecker",
    "TCPChecker",
    "DiskChecker",
    "MemoryChecker",
    "CPUChecker",
    "CustomChecker",
    # 自动恢复
    "AutoRecovery",
    # 管理器
    "HealthManager",
    "health_manager",
    # 路由
    "create_health_routes",
]
