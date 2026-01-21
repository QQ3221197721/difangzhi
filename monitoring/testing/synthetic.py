# 地方志数据智能管理系统 - 合成监控
"""合成监控：模拟用户行为进行端到端测试"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import httpx
import structlog

logger = structlog.get_logger()


class CheckType(str, Enum):
    HTTP = "http"
    TCP = "tcp"
    DNS = "dns"
    SSL = "ssl"


@dataclass
class SyntheticCheck:
    """合成检查配置"""
    name: str
    check_type: CheckType
    target: str
    interval_seconds: int = 60
    timeout_seconds: int = 10
    expected_status: int = 200
    expected_body_contains: Optional[str] = None
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        self.headers = self.headers or {}


@dataclass
class CheckResult:
    """检查结果"""
    check_name: str
    success: bool
    response_time_ms: float
    status_code: Optional[int] = None
    error: Optional[str] = None
    timestamp: str = ""
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        self.details = self.details or {}


class SyntheticMonitor:
    """合成监控器"""
    
    def __init__(self, checks: List[SyntheticCheck] = None):
        self.checks = checks or []
        self.results_history: List[CheckResult] = []
        self.client = httpx.AsyncClient()
        self._running = False
        self._callbacks: List[Callable[[CheckResult], None]] = []
    
    def add_check(self, check: SyntheticCheck):
        """添加检查"""
        self.checks.append(check)
    
    def on_result(self, callback: Callable[[CheckResult], None]):
        """注册结果回调"""
        self._callbacks.append(callback)
    
    async def run_http_check(self, check: SyntheticCheck) -> CheckResult:
        """执行HTTP检查"""
        start = time.time()
        try:
            response = await self.client.get(
                check.target,
                headers=check.headers,
                timeout=check.timeout_seconds
            )
            duration = (time.time() - start) * 1000
            
            success = response.status_code == check.expected_status
            
            if check.expected_body_contains and success:
                success = check.expected_body_contains in response.text
            
            return CheckResult(
                check_name=check.name,
                success=success,
                response_time_ms=duration,
                status_code=response.status_code,
                details={
                    "content_length": len(response.content),
                    "headers": dict(response.headers)
                }
            )
        except httpx.TimeoutException:
            return CheckResult(
                check_name=check.name,
                success=False,
                response_time_ms=check.timeout_seconds * 1000,
                error="Timeout"
            )
        except Exception as e:
            return CheckResult(
                check_name=check.name,
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def run_tcp_check(self, check: SyntheticCheck) -> CheckResult:
        """执行TCP连接检查"""
        start = time.time()
        try:
            host, port = check.target.split(":")
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port)),
                timeout=check.timeout_seconds
            )
            writer.close()
            await writer.wait_closed()
            
            return CheckResult(
                check_name=check.name,
                success=True,
                response_time_ms=(time.time() - start) * 1000
            )
        except asyncio.TimeoutError:
            return CheckResult(
                check_name=check.name,
                success=False,
                response_time_ms=check.timeout_seconds * 1000,
                error="Connection timeout"
            )
        except Exception as e:
            return CheckResult(
                check_name=check.name,
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def run_ssl_check(self, check: SyntheticCheck) -> CheckResult:
        """执行SSL证书检查"""
        import ssl
        import socket
        from datetime import datetime
        
        start = time.time()
        try:
            context = ssl.create_default_context()
            hostname = check.target.replace("https://", "").split("/")[0]
            
            with socket.create_connection((hostname, 443), timeout=check.timeout_seconds) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
            # 检查证书过期时间
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_until_expiry = (not_after - datetime.now()).days
            
            return CheckResult(
                check_name=check.name,
                success=days_until_expiry > 7,  # 7天内过期算失败
                response_time_ms=(time.time() - start) * 1000,
                details={
                    "issuer": dict(x[0] for x in cert['issuer']),
                    "subject": dict(x[0] for x in cert['subject']),
                    "not_after": not_after.isoformat(),
                    "days_until_expiry": days_until_expiry
                }
            )
        except Exception as e:
            return CheckResult(
                check_name=check.name,
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def run_check(self, check: SyntheticCheck) -> CheckResult:
        """运行单个检查"""
        if check.check_type == CheckType.HTTP:
            return await self.run_http_check(check)
        elif check.check_type == CheckType.TCP:
            return await self.run_tcp_check(check)
        elif check.check_type == CheckType.SSL:
            return await self.run_ssl_check(check)
        else:
            return CheckResult(
                check_name=check.name,
                success=False,
                response_time_ms=0,
                error=f"Unsupported check type: {check.check_type}"
            )
    
    async def run_all_checks(self) -> List[CheckResult]:
        """运行所有检查"""
        tasks = [self.run_check(check) for check in self.checks]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            self.results_history.append(result)
            for callback in self._callbacks:
                callback(result)
        
        return list(results)
    
    async def start_continuous_monitoring(self):
        """启动持续监控"""
        self._running = True
        logger.info("Starting synthetic monitoring", checks=len(self.checks))
        
        while self._running:
            await self.run_all_checks()
            
            # 找到最小间隔
            min_interval = min(c.interval_seconds for c in self.checks) if self.checks else 60
            await asyncio.sleep(min_interval)
    
    def stop(self):
        """停止监控"""
        self._running = False
        logger.info("Stopping synthetic monitoring")
    
    def get_availability(self, check_name: str, hours: int = 24) -> float:
        """计算可用性百分比"""
        cutoff = datetime.now().timestamp() - hours * 3600
        relevant_results = [
            r for r in self.results_history
            if r.check_name == check_name and 
            datetime.fromisoformat(r.timestamp).timestamp() > cutoff
        ]
        
        if not relevant_results:
            return 100.0
        
        successful = sum(1 for r in relevant_results if r.success)
        return successful / len(relevant_results) * 100
    
    def get_avg_response_time(self, check_name: str, hours: int = 24) -> float:
        """计算平均响应时间"""
        cutoff = datetime.now().timestamp() - hours * 3600
        relevant_results = [
            r for r in self.results_history
            if r.check_name == check_name and 
            r.success and
            datetime.fromisoformat(r.timestamp).timestamp() > cutoff
        ]
        
        if not relevant_results:
            return 0.0
        
        return sum(r.response_time_ms for r in relevant_results) / len(relevant_results)


# 预定义的检查配置
DEFAULT_CHECKS = [
    SyntheticCheck(
        name="api_health",
        check_type=CheckType.HTTP,
        target="http://localhost:8000/health",
        interval_seconds=30,
        expected_status=200,
        expected_body_contains="ok"
    ),
    SyntheticCheck(
        name="api_docs",
        check_type=CheckType.HTTP,
        target="http://localhost:8000/docs",
        interval_seconds=60,
        expected_status=200
    ),
    SyntheticCheck(
        name="frontend",
        check_type=CheckType.HTTP,
        target="http://localhost:5173",
        interval_seconds=60,
        expected_status=200
    ),
    SyntheticCheck(
        name="database",
        check_type=CheckType.TCP,
        target="localhost:5432",
        interval_seconds=30
    ),
    SyntheticCheck(
        name="redis",
        check_type=CheckType.TCP,
        target="localhost:6379",
        interval_seconds=30
    ),
]
