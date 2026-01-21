# 地方志数据智能管理系统 - 压力测试
"""渐进式压力测试"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class StressConfig:
    """压力测试配置"""
    name: str = "stress_test"
    base_url: str = "http://localhost:8000"
    
    # 起始并发数
    initial_users: int = 1
    # 最大并发数
    max_users: int = 100
    # 每步增加的用户数
    step_users: int = 10
    # 每步持续时间（秒）
    step_duration: int = 30
    
    # 停止条件
    max_error_rate: float = 0.1  # 错误率阈值
    max_response_time: float = 5000  # 响应时间阈值(ms)
    
    # 请求配置
    timeout: float = 30.0
    think_time: float = 1.0  # 用户思考时间


@dataclass
class StressStep:
    """压力测试阶段"""
    users: int
    start_time: datetime
    end_time: Optional[datetime] = None
    requests_total: int = 0
    requests_success: int = 0
    latency_sum: float = 0
    latency_max: float = 0
    
    @property
    def error_rate(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return 1 - (self.requests_success / self.requests_total)
    
    @property
    def latency_avg(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return self.latency_sum / self.requests_total


@dataclass
class StressResult:
    """压力测试结果"""
    config: StressConfig
    start_time: datetime
    end_time: datetime
    steps: List[StressStep] = field(default_factory=list)
    breaking_point: Optional[int] = None  # 崩溃点用户数
    max_sustainable_users: int = 0  # 最大可持续用户数
    reason_stopped: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "name": self.config.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "breaking_point": self.breaking_point,
            "max_sustainable_users": self.max_sustainable_users,
            "reason_stopped": self.reason_stopped,
            "steps": [
                {
                    "users": s.users,
                    "requests": s.requests_total,
                    "success_rate": f"{(1-s.error_rate)*100:.1f}%",
                    "latency_avg_ms": round(s.latency_avg, 2),
                    "latency_max_ms": round(s.latency_max, 2),
                }
                for s in self.steps
            ]
        }


class StressTest:
    """压力测试"""
    
    def __init__(self, config: StressConfig):
        self.config = config
        self.result: Optional[StressResult] = None
        self._running = False
        self._current_step: Optional[StressStep] = None
    
    async def run(
        self,
        endpoint: str,
        method: str = "GET",
        data: Any = None
    ) -> StressResult:
        """运行压力测试"""
        logger.info(
            "开始压力测试",
            name=self.config.name,
            endpoint=endpoint,
            max_users=self.config.max_users
        )
        
        self.result = StressResult(
            config=self.config,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        self._running = True
        current_users = self.config.initial_users
        url = f"{self.config.base_url}{endpoint}"
        
        try:
            while self._running and current_users <= self.config.max_users:
                # 创建当前阶段
                self._current_step = StressStep(
                    users=current_users,
                    start_time=datetime.now()
                )
                
                logger.info(f"压力阶段: {current_users} 用户")
                
                # 运行当前阶段
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    await self._run_step(client, url, method, data, current_users)
                
                self._current_step.end_time = datetime.now()
                self.result.steps.append(self._current_step)
                
                # 检查停止条件
                if self._should_stop():
                    self.result.breaking_point = current_users
                    self.result.reason_stopped = self._get_stop_reason()
                    break
                
                self.result.max_sustainable_users = current_users
                current_users += self.config.step_users
            
            if not self.result.reason_stopped:
                self.result.reason_stopped = "达到最大用户数"
        
        finally:
            self._running = False
            self.result.end_time = datetime.now()
        
        return self.result
    
    async def _run_step(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str,
        data: Any,
        num_users: int
    ):
        """运行单个阶段"""
        start_time = time.time()
        tasks = []
        
        async def user_simulation():
            """模拟单个用户"""
            while time.time() - start_time < self.config.step_duration:
                if not self._running:
                    break
                
                req_start = time.time()
                try:
                    if method.upper() == "GET":
                        response = await client.get(url)
                    else:
                        response = await client.post(url, json=data)
                    
                    latency = (time.time() - req_start) * 1000
                    success = 200 <= response.status_code < 400
                    
                    self._current_step.requests_total += 1
                    self._current_step.latency_sum += latency
                    self._current_step.latency_max = max(
                        self._current_step.latency_max, latency
                    )
                    
                    if success:
                        self._current_step.requests_success += 1
                
                except Exception:
                    self._current_step.requests_total += 1
                
                # 思考时间
                await asyncio.sleep(self.config.think_time)
        
        # 启动用户模拟
        for _ in range(num_users):
            tasks.append(asyncio.create_task(user_simulation()))
        
        await asyncio.gather(*tasks)
    
    def _should_stop(self) -> bool:
        """检查是否应该停止"""
        if not self._current_step:
            return False
        
        # 错误率过高
        if self._current_step.error_rate > self.config.max_error_rate:
            return True
        
        # 响应时间过长
        if self._current_step.latency_avg > self.config.max_response_time:
            return True
        
        return False
    
    def _get_stop_reason(self) -> str:
        """获取停止原因"""
        if not self._current_step:
            return "未知"
        
        if self._current_step.error_rate > self.config.max_error_rate:
            return f"错误率过高: {self._current_step.error_rate*100:.1f}%"
        
        if self._current_step.latency_avg > self.config.max_response_time:
            return f"响应时间过长: {self._current_step.latency_avg:.0f}ms"
        
        return "达到限制"
    
    async def stop(self):
        """停止测试"""
        self._running = False


def generate_stress_report(result: StressResult) -> str:
    """生成压力测试报告"""
    report = f"""
# 压力测试报告

## 基本信息
- 测试名称: {result.config.name}
- 开始时间: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- 结束时间: {result.end_time.strftime('%Y-%m-%d %H:%M:%S')}
- 总耗时: {(result.end_time - result.start_time).total_seconds():.0f}秒

## 结果摘要
- 最大可持续用户数: {result.max_sustainable_users}
- 崩溃点: {result.breaking_point or 'N/A'}
- 停止原因: {result.reason_stopped}

## 阶段详情

| 用户数 | 请求数 | 成功率 | 平均延迟 | 最大延迟 |
|--------|--------|--------|----------|----------|
"""
    
    for step in result.steps:
        report += f"| {step.users} | {step.requests_total} | "
        report += f"{(1-step.error_rate)*100:.1f}% | "
        report += f"{step.latency_avg:.0f}ms | "
        report += f"{step.latency_max:.0f}ms |\n"
    
    return report
