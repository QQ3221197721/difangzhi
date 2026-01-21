# 地方志数据智能管理系统 - 灰度发布
"""金丝雀发布管理"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class CanaryPhase(str, Enum):
    """灰度阶段"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    CANARY_1 = "canary_1"    # 1%流量
    CANARY_5 = "canary_5"    # 5%流量
    CANARY_10 = "canary_10"  # 10%流量
    CANARY_25 = "canary_25"  # 25%流量
    CANARY_50 = "canary_50"  # 50%流量
    CANARY_75 = "canary_75"  # 75%流量
    FULL = "full"            # 100%流量
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"


@dataclass
class CanaryConfig:
    """灰度配置"""
    name: str
    target_version: str
    baseline_version: str
    # 流量比例阶段
    phases: List[int] = field(default_factory=lambda: [1, 5, 10, 25, 50, 75, 100])
    # 每阶段持续时间（秒）
    phase_duration: int = 300  # 5分钟
    # 自动推进
    auto_promote: bool = True
    # 成功标准
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    # 回滚标准
    rollback_criteria: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.success_criteria:
            self.success_criteria = {
                "error_rate_threshold": 0.01,  # 错误率阈值 1%
                "latency_p95_threshold": 1000,  # P95延迟阈值 1秒
                "min_requests": 100,  # 最小请求数
            }
        if not self.rollback_criteria:
            self.rollback_criteria = {
                "error_rate_threshold": 0.05,  # 错误率超5%回滚
                "latency_p95_threshold": 3000,  # P95超3秒回滚
            }


@dataclass
class CanaryMetrics:
    """灰度指标"""
    requests_total: int = 0
    errors_total: int = 0
    latency_sum_ms: float = 0
    latency_samples: List[float] = field(default_factory=list)
    
    @property
    def error_rate(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return self.errors_total / self.requests_total
    
    @property
    def latency_avg(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return self.latency_sum_ms / self.requests_total
    
    @property
    def latency_p95(self) -> float:
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    def record_request(self, success: bool, latency_ms: float):
        self.requests_total += 1
        self.latency_sum_ms += latency_ms
        self.latency_samples.append(latency_ms)
        if not success:
            self.errors_total += 1
        # 保持采样窗口
        if len(self.latency_samples) > 10000:
            self.latency_samples = self.latency_samples[-5000:]
    
    def reset(self):
        self.requests_total = 0
        self.errors_total = 0
        self.latency_sum_ms = 0
        self.latency_samples.clear()


class CanaryDeployment:
    """灰度发布管理"""
    
    def __init__(self, config: CanaryConfig):
        self.config = config
        self.phase = CanaryPhase.PENDING
        self.current_weight = 0
        self.phase_index = -1
        self.start_time: Optional[datetime] = None
        self.phase_start_time: Optional[datetime] = None
        
        # 指标
        self.canary_metrics = CanaryMetrics()
        self.baseline_metrics = CanaryMetrics()
        
        # 回调
        self._on_phase_change: List[Callable] = []
        self._on_rollback: List[Callable] = []
        self._on_complete: List[Callable] = []
        
        # 运行状态
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def on_phase_change(self, callback: Callable):
        """注册阶段变更回调"""
        self._on_phase_change.append(callback)
    
    def on_rollback(self, callback: Callable):
        """注册回滚回调"""
        self._on_rollback.append(callback)
    
    def on_complete(self, callback: Callable):
        """注册完成回调"""
        self._on_complete.append(callback)
    
    async def start(self):
        """开始灰度发布"""
        logger.info(
            "开始灰度发布",
            name=self.config.name,
            target=self.config.target_version,
            baseline=self.config.baseline_version
        )
        
        self.phase = CanaryPhase.INITIALIZING
        self.start_time = datetime.now()
        self._running = True
        
        # 进入第一阶段
        await self._advance_phase()
        
        # 启动监控任务
        if self.config.auto_promote:
            self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """停止灰度发布"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _advance_phase(self):
        """推进到下一阶段"""
        self.phase_index += 1
        
        if self.phase_index >= len(self.config.phases):
            await self._complete()
            return
        
        self.current_weight = self.config.phases[self.phase_index]
        self.phase_start_time = datetime.now()
        
        # 更新阶段状态
        if self.current_weight == 100:
            self.phase = CanaryPhase.FULL
        else:
            self.phase = CanaryPhase(f"canary_{self.current_weight}")
        
        # 重置指标
        self.canary_metrics.reset()
        self.baseline_metrics.reset()
        
        logger.info(
            "灰度阶段推进",
            phase=self.phase.value,
            weight=self.current_weight
        )
        
        # 触发回调
        for callback in self._on_phase_change:
            await self._call_callback(callback, self.phase, self.current_weight)
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            await asyncio.sleep(10)  # 每10秒检查一次
            
            # 检查是否需要回滚
            if self._should_rollback():
                await self.rollback("指标异常触发自动回滚")
                return
            
            # 检查是否可以推进
            if self._can_promote():
                phase_elapsed = (datetime.now() - self.phase_start_time).total_seconds()
                if phase_elapsed >= self.config.phase_duration:
                    await self._advance_phase()
    
    def _should_rollback(self) -> bool:
        """检查是否应该回滚"""
        criteria = self.config.rollback_criteria
        
        # 检查错误率
        if self.canary_metrics.error_rate > criteria.get("error_rate_threshold", 0.05):
            logger.warning(
                "错误率超过阈值",
                error_rate=self.canary_metrics.error_rate,
                threshold=criteria["error_rate_threshold"]
            )
            return True
        
        # 检查延迟
        if self.canary_metrics.latency_p95 > criteria.get("latency_p95_threshold", 3000):
            logger.warning(
                "P95延迟超过阈值",
                latency_p95=self.canary_metrics.latency_p95,
                threshold=criteria["latency_p95_threshold"]
            )
            return True
        
        return False
    
    def _can_promote(self) -> bool:
        """检查是否可以推进"""
        criteria = self.config.success_criteria
        
        # 检查最小请求数
        if self.canary_metrics.requests_total < criteria.get("min_requests", 100):
            return False
        
        # 检查错误率
        if self.canary_metrics.error_rate > criteria.get("error_rate_threshold", 0.01):
            return False
        
        # 检查延迟
        if self.canary_metrics.latency_p95 > criteria.get("latency_p95_threshold", 1000):
            return False
        
        return True
    
    async def rollback(self, reason: str):
        """回滚"""
        logger.warning(
            "执行灰度回滚",
            name=self.config.name,
            reason=reason,
            phase=self.phase.value
        )
        
        self.phase = CanaryPhase.ROLLED_BACK
        self.current_weight = 0
        self._running = False
        
        # 触发回调
        for callback in self._on_rollback:
            await self._call_callback(callback, reason)
    
    async def _complete(self):
        """完成灰度"""
        logger.info(
            "灰度发布完成",
            name=self.config.name,
            target=self.config.target_version,
            duration=str(datetime.now() - self.start_time)
        )
        
        self.phase = CanaryPhase.COMPLETED
        self._running = False
        
        # 触发回调
        for callback in self._on_complete:
            await self._call_callback(callback)
    
    async def manual_promote(self):
        """手动推进"""
        if not self._running:
            raise RuntimeError("灰度发布未运行")
        await self._advance_phase()
    
    async def manual_rollback(self, reason: str = "手动回滚"):
        """手动回滚"""
        await self.rollback(reason)
    
    async def _call_callback(self, callback: Callable, *args):
        """调用回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error("回调执行失败", error=str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "name": self.config.name,
            "phase": self.phase.value,
            "current_weight": self.current_weight,
            "target_version": self.config.target_version,
            "baseline_version": self.config.baseline_version,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "canary_metrics": {
                "requests": self.canary_metrics.requests_total,
                "error_rate": self.canary_metrics.error_rate,
                "latency_avg": self.canary_metrics.latency_avg,
                "latency_p95": self.canary_metrics.latency_p95,
            },
            "baseline_metrics": {
                "requests": self.baseline_metrics.requests_total,
                "error_rate": self.baseline_metrics.error_rate,
                "latency_avg": self.baseline_metrics.latency_avg,
                "latency_p95": self.baseline_metrics.latency_p95,
            }
        }
