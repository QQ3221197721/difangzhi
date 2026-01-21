# 地方志数据智能管理系统 - 性能基准测试
"""API性能基准测试"""

import asyncio
import time
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger()


class LoadProfile(str, Enum):
    """负载模式"""
    CONSTANT = "constant"      # 恒定负载
    RAMP_UP = "ramp_up"        # 渐增
    SPIKE = "spike"            # 尖峰
    STEP = "step"              # 阶梯
    WAVE = "wave"              # 波浪


@dataclass
class BenchmarkConfig:
    """基准测试配置"""
    name: str = "benchmark"
    base_url: str = "http://localhost:8000"
    # 并发数
    concurrency: int = 10
    # 总请求数
    total_requests: int = 1000
    # 持续时间（秒）
    duration: int = 60
    # 负载模式
    load_profile: LoadProfile = LoadProfile.CONSTANT
    # 请求超时（秒）
    timeout: float = 30.0
    # 预热请求数
    warmup_requests: int = 10
    # 目标RPS
    target_rps: int = 0
    # 请求头
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class RequestResult:
    """请求结果"""
    success: bool
    status_code: int
    latency_ms: float
    response_size: int
    error: Optional[str] = None
    timestamp: float = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    config: BenchmarkConfig
    start_time: datetime
    end_time: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    # 延迟统计（毫秒）
    latency_min: float
    latency_max: float
    latency_avg: float
    latency_median: float
    latency_p90: float
    latency_p95: float
    latency_p99: float
    # 吞吐量
    requests_per_second: float
    bytes_per_second: float
    # 错误分布
    error_distribution: Dict[str, int] = field(default_factory=dict)
    # 状态码分布
    status_distribution: Dict[int, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.config.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{self.successful_requests/self.total_requests*100:.2f}%",
            "latency": {
                "min_ms": round(self.latency_min, 2),
                "max_ms": round(self.latency_max, 2),
                "avg_ms": round(self.latency_avg, 2),
                "median_ms": round(self.latency_median, 2),
                "p90_ms": round(self.latency_p90, 2),
                "p95_ms": round(self.latency_p95, 2),
                "p99_ms": round(self.latency_p99, 2),
            },
            "throughput": {
                "rps": round(self.requests_per_second, 2),
                "bytes_per_second": round(self.bytes_per_second, 2),
            },
            "error_distribution": self.error_distribution,
            "status_distribution": self.status_distribution,
        }


class BenchmarkRunner:
    """基准测试运行器"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.results: List[RequestResult] = []
        self._running = False
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    async def run_single_request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        method: str = "GET",
        data: Any = None
    ) -> RequestResult:
        """执行单个请求"""
        start = time.time()
        try:
            if method.upper() == "GET":
                response = await client.get(endpoint)
            elif method.upper() == "POST":
                response = await client.post(endpoint, json=data)
            else:
                response = await client.request(method, endpoint, json=data)
            
            latency = (time.time() - start) * 1000
            return RequestResult(
                success=200 <= response.status_code < 400,
                status_code=response.status_code,
                latency_ms=latency,
                response_size=len(response.content)
            )
        except httpx.TimeoutException:
            return RequestResult(
                success=False,
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_size=0,
                error="Timeout"
            )
        except Exception as e:
            return RequestResult(
                success=False,
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_size=0,
                error=str(e)
            )
    
    async def _worker(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        method: str,
        data: Any,
        results: List[RequestResult]
    ):
        """工作协程"""
        async with self._semaphore:
            result = await self.run_single_request(client, endpoint, method, data)
            results.append(result)
    
    async def run(
        self,
        endpoint: str,
        method: str = "GET",
        data: Any = None
    ) -> BenchmarkResult:
        """运行基准测试"""
        logger.info(
            "开始基准测试",
            name=self.config.name,
            endpoint=endpoint,
            concurrency=self.config.concurrency,
            total=self.config.total_requests
        )
        
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        self.results = []
        
        url = f"{self.config.base_url}{endpoint}"
        start_time = datetime.now()
        
        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            headers=self.config.headers
        ) as client:
            # 预热
            if self.config.warmup_requests > 0:
                logger.info("预热中...", warmup=self.config.warmup_requests)
                for _ in range(self.config.warmup_requests):
                    await self.run_single_request(client, url, method, data)
            
            # 正式测试
            tasks = []
            for _ in range(self.config.total_requests):
                task = asyncio.create_task(
                    self._worker(client, url, method, data, self.results)
                )
                tasks.append(task)
                
                # 控制RPS
                if self.config.target_rps > 0:
                    await asyncio.sleep(1 / self.config.target_rps)
            
            await asyncio.gather(*tasks)
        
        end_time = datetime.now()
        
        return self._calculate_result(start_time, end_time)
    
    def _calculate_result(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> BenchmarkResult:
        """计算测试结果"""
        duration = (end_time - start_time).total_seconds()
        
        latencies = [r.latency_ms for r in self.results]
        latencies.sort()
        
        successful = [r for r in self.results if r.success]
        total_bytes = sum(r.response_size for r in successful)
        
        # 错误分布
        error_dist: Dict[str, int] = {}
        for r in self.results:
            if r.error:
                error_dist[r.error] = error_dist.get(r.error, 0) + 1
        
        # 状态码分布
        status_dist: Dict[int, int] = {}
        for r in self.results:
            status_dist[r.status_code] = status_dist.get(r.status_code, 0) + 1
        
        def percentile(data: List[float], p: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = f + 1
            if f == len(data) - 1:
                return data[f]
            return data[f] * (c - k) + data[c] * (k - f)
        
        return BenchmarkResult(
            config=self.config,
            start_time=start_time,
            end_time=end_time,
            total_requests=len(self.results),
            successful_requests=len(successful),
            failed_requests=len(self.results) - len(successful),
            latency_min=min(latencies) if latencies else 0,
            latency_max=max(latencies) if latencies else 0,
            latency_avg=statistics.mean(latencies) if latencies else 0,
            latency_median=statistics.median(latencies) if latencies else 0,
            latency_p90=percentile(latencies, 90),
            latency_p95=percentile(latencies, 95),
            latency_p99=percentile(latencies, 99),
            requests_per_second=len(self.results) / duration if duration > 0 else 0,
            bytes_per_second=total_bytes / duration if duration > 0 else 0,
            error_distribution=error_dist,
            status_distribution=status_dist
        )


# 预定义的测试场景
BENCHMARK_SCENARIOS = {
    "health_check": {
        "endpoint": "/health",
        "method": "GET",
        "config": BenchmarkConfig(
            name="health_check",
            concurrency=50,
            total_requests=5000,
        )
    },
    "document_list": {
        "endpoint": "/api/documents",
        "method": "GET",
        "config": BenchmarkConfig(
            name="document_list",
            concurrency=20,
            total_requests=1000,
        )
    },
    "search": {
        "endpoint": "/api/documents/search",
        "method": "POST",
        "data": {"query": "测试"},
        "config": BenchmarkConfig(
            name="search",
            concurrency=10,
            total_requests=500,
        )
    },
}
