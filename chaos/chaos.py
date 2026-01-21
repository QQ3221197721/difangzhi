# 地方志数据智能管理系统 - 混沌工程
"""故障注入和韧性测试"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class FailureMode(str, Enum):
    """故障模式"""
    NETWORK_LATENCY = "network_latency"      # 网络延迟
    NETWORK_LOSS = "network_loss"            # 网络丢包
    NETWORK_PARTITION = "network_partition"  # 网络分区
    SERVICE_KILL = "service_kill"            # 服务终止
    SERVICE_PAUSE = "service_pause"          # 服务暂停
    CPU_STRESS = "cpu_stress"                # CPU压力
    MEMORY_STRESS = "memory_stress"          # 内存压力
    DISK_STRESS = "disk_stress"              # 磁盘压力
    DNS_FAILURE = "dns_failure"              # DNS故障
    HTTP_ERROR = "http_error"                # HTTP错误注入


@dataclass
class ChaosConfig:
    """混沌实验配置"""
    name: str
    target: str  # 目标服务/容器
    failure_mode: FailureMode
    duration: int = 60  # 持续时间（秒）
    intensity: float = 0.5  # 强度(0-1)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # 安全配置
    max_duration: int = 300  # 最大持续时间
    auto_rollback: bool = True
    
    # 调度
    schedule: Optional[str] = None  # cron表达式
    
    def __post_init__(self):
        # 参数默认值
        defaults = {
            FailureMode.NETWORK_LATENCY: {"latency_ms": 100, "jitter_ms": 20},
            FailureMode.NETWORK_LOSS: {"loss_percent": 10},
            FailureMode.CPU_STRESS: {"load_percent": 80},
            FailureMode.MEMORY_STRESS: {"memory_mb": 512},
            FailureMode.HTTP_ERROR: {"error_code": 500, "error_rate": 0.1},
        }
        if self.failure_mode in defaults:
            for k, v in defaults[self.failure_mode].items():
                self.parameters.setdefault(k, v)


@dataclass
class ChaosEvent:
    """混沌事件"""
    timestamp: datetime
    event_type: str  # started/ended/impact_detected/rollback
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChaosReport:
    """混沌实验报告"""
    config: ChaosConfig
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # running/completed/failed/rolled_back
    events: List[ChaosEvent] = field(default_factory=list)
    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_during: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)
    
    def add_event(self, event_type: str, message: str, details: Dict = None):
        self.events.append(ChaosEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            message=message,
            details=details or {}
        ))
    
    def to_dict(self) -> Dict:
        return {
            "experiment": self.config.name,
            "target": self.config.target,
            "failure_mode": self.config.failure_mode.value,
            "duration_seconds": self.config.duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "type": e.event_type,
                    "message": e.message,
                    "details": e.details
                }
                for e in self.events
            ],
            "metrics": {
                "before": self.metrics_before,
                "during": self.metrics_during,
                "after": self.metrics_after
            },
            "findings": self.findings
        }


class ChaosExperiment:
    """混沌实验"""
    
    def __init__(self, config: ChaosConfig):
        self.config = config
        self.report: Optional[ChaosReport] = None
        self._running = False
        self._rollback_handlers: Dict[FailureMode, Callable] = {}
        
        # 注册回滚处理器
        self._register_rollback_handlers()
    
    def _register_rollback_handlers(self):
        """注册回滚处理器"""
        self._rollback_handlers = {
            FailureMode.NETWORK_LATENCY: self._rollback_network,
            FailureMode.NETWORK_LOSS: self._rollback_network,
            FailureMode.SERVICE_PAUSE: self._rollback_service_pause,
            FailureMode.CPU_STRESS: self._rollback_stress,
            FailureMode.MEMORY_STRESS: self._rollback_stress,
        }
    
    async def start(self) -> ChaosReport:
        """开始实验"""
        logger.info(
            "开始混沌实验",
            name=self.config.name,
            target=self.config.target,
            mode=self.config.failure_mode.value
        )
        
        self.report = ChaosReport(
            config=self.config,
            start_time=datetime.now(),
            end_time=None,
            status="running"
        )
        self.report.add_event("started", f"混沌实验开始: {self.config.name}")
        
        self._running = True
        
        try:
            # 收集基线指标
            self.report.metrics_before = await self._collect_metrics()
            
            # 注入故障
            await self._inject_failure()
            self.report.add_event("injected", f"故障注入成功: {self.config.failure_mode.value}")
            
            # 等待实验持续时间
            await self._run_experiment()
            
            # 收集恢复后指标
            self.report.metrics_after = await self._collect_metrics()
            
            # 分析结果
            self._analyze_results()
            
            self.report.status = "completed"
            self.report.add_event("completed", "混沌实验完成")
            
        except Exception as e:
            logger.error("混沌实验异常", error=str(e))
            self.report.status = "failed"
            self.report.add_event("failed", f"实验失败: {e}")
            
            if self.config.auto_rollback:
                await self._rollback()
        
        finally:
            self._running = False
            self.report.end_time = datetime.now()
        
        return self.report
    
    async def stop(self):
        """停止实验"""
        if self._running:
            self._running = False
            await self._rollback()
            self.report.status = "stopped"
            self.report.add_event("stopped", "实验被手动停止")
    
    async def _inject_failure(self):
        """注入故障"""
        mode = self.config.failure_mode
        params = self.config.parameters
        
        if mode == FailureMode.NETWORK_LATENCY:
            await self._inject_network_latency(params)
        elif mode == FailureMode.NETWORK_LOSS:
            await self._inject_network_loss(params)
        elif mode == FailureMode.SERVICE_PAUSE:
            await self._inject_service_pause()
        elif mode == FailureMode.CPU_STRESS:
            await self._inject_cpu_stress(params)
        elif mode == FailureMode.MEMORY_STRESS:
            await self._inject_memory_stress(params)
        elif mode == FailureMode.HTTP_ERROR:
            await self._inject_http_error(params)
        else:
            logger.warning(f"未实现的故障模式: {mode}")
    
    async def _inject_network_latency(self, params: Dict):
        """注入网络延迟"""
        latency = params.get("latency_ms", 100)
        jitter = params.get("jitter_ms", 20)
        
        # 使用tc命令注入延迟(需要root权限)
        cmd = f"tc qdisc add dev eth0 root netem delay {latency}ms {jitter}ms"
        logger.info(f"注入网络延迟: {latency}ms ± {jitter}ms")
        # 实际执行: subprocess.run(cmd, shell=True)
        await asyncio.sleep(0.5)
    
    async def _inject_network_loss(self, params: Dict):
        """注入网络丢包"""
        loss = params.get("loss_percent", 10)
        
        cmd = f"tc qdisc add dev eth0 root netem loss {loss}%"
        logger.info(f"注入网络丢包: {loss}%")
        await asyncio.sleep(0.5)
    
    async def _inject_service_pause(self):
        """暂停服务"""
        # docker pause 或 kill -STOP
        logger.info(f"暂停服务: {self.config.target}")
        await asyncio.sleep(0.5)
    
    async def _inject_cpu_stress(self, params: Dict):
        """注入CPU压力"""
        load = params.get("load_percent", 80)
        
        # 使用stress-ng工具
        logger.info(f"注入CPU压力: {load}%")
        await asyncio.sleep(0.5)
    
    async def _inject_memory_stress(self, params: Dict):
        """注入内存压力"""
        memory = params.get("memory_mb", 512)
        
        logger.info(f"注入内存压力: {memory}MB")
        await asyncio.sleep(0.5)
    
    async def _inject_http_error(self, params: Dict):
        """注入HTTP错误"""
        error_code = params.get("error_code", 500)
        error_rate = params.get("error_rate", 0.1)
        
        logger.info(f"注入HTTP错误: {error_code}, 错误率: {error_rate*100}%")
        # 这通常需要在应用层或代理层实现
        await asyncio.sleep(0.5)
    
    async def _run_experiment(self):
        """运行实验"""
        start = datetime.now()
        
        while self._running:
            elapsed = (datetime.now() - start).total_seconds()
            
            if elapsed >= self.config.duration:
                break
            
            # 定期收集指标
            metrics = await self._collect_metrics()
            self.report.metrics_during = metrics
            
            # 检查是否需要自动回滚
            if self._should_auto_rollback(metrics):
                logger.warning("检测到严重影响，执行自动回滚")
                await self._rollback()
                self.report.status = "rolled_back"
                self.report.add_event("rolled_back", "检测到严重影响，自动回滚")
                break
            
            await asyncio.sleep(5)  # 每5秒检查一次
        
        # 清理故障
        await self._cleanup()
    
    def _should_auto_rollback(self, metrics: Dict) -> bool:
        """检查是否需要自动回滚"""
        # 检查错误率
        if metrics.get("error_rate", 0) > 0.5:  # 错误率超过50%
            return True
        
        # 检查服务可用性
        if not metrics.get("health", True):
            return True
        
        return False
    
    async def _rollback(self):
        """回滚故障"""
        handler = self._rollback_handlers.get(self.config.failure_mode)
        if handler:
            await handler()
        await self._cleanup()
    
    async def _rollback_network(self):
        """回滚网络故障"""
        cmd = "tc qdisc del dev eth0 root"
        logger.info("回滚网络配置")
        await asyncio.sleep(0.5)
    
    async def _rollback_service_pause(self):
        """回滚服务暂停"""
        logger.info(f"恢复服务: {self.config.target}")
        await asyncio.sleep(0.5)
    
    async def _rollback_stress(self):
        """回滚压力测试"""
        logger.info("停止压力测试")
        await asyncio.sleep(0.5)
    
    async def _cleanup(self):
        """清理"""
        logger.info("清理混沌实验环境")
    
    async def _collect_metrics(self) -> Dict[str, Any]:
        """收集指标"""
        # 这里应该从Prometheus等监控系统收集
        return {
            "timestamp": datetime.now().isoformat(),
            "health": True,
            "error_rate": random.uniform(0, 0.1),
            "latency_p95": random.uniform(50, 200),
            "requests_per_second": random.uniform(50, 100),
        }
    
    def _analyze_results(self):
        """分析结果"""
        before = self.report.metrics_before
        during = self.report.metrics_during
        after = self.report.metrics_after
        
        findings = []
        
        # 分析延迟变化
        latency_increase = (
            during.get("latency_p95", 0) - before.get("latency_p95", 0)
        ) / max(before.get("latency_p95", 1), 1) * 100
        
        if latency_increase > 50:
            findings.append(f"延迟增加显著: {latency_increase:.1f}%")
        
        # 分析错误率变化
        error_increase = during.get("error_rate", 0) - before.get("error_rate", 0)
        if error_increase > 0.05:
            findings.append(f"错误率增加: {error_increase*100:.1f}%")
        
        # 分析恢复情况
        recovery_time = (
            self.report.end_time - self.report.start_time
        ).total_seconds() - self.config.duration
        
        if recovery_time > 30:
            findings.append(f"恢复时间较长: {recovery_time:.0f}秒")
        
        self.report.findings = findings


# 预定义的混沌实验场景
CHAOS_SCENARIOS = {
    "database_latency": ChaosConfig(
        name="数据库延迟",
        target="postgres",
        failure_mode=FailureMode.NETWORK_LATENCY,
        duration=60,
        parameters={"latency_ms": 200, "jitter_ms": 50}
    ),
    "api_error_injection": ChaosConfig(
        name="API错误注入",
        target="backend",
        failure_mode=FailureMode.HTTP_ERROR,
        duration=120,
        parameters={"error_code": 503, "error_rate": 0.2}
    ),
    "memory_pressure": ChaosConfig(
        name="内存压力",
        target="backend",
        failure_mode=FailureMode.MEMORY_STRESS,
        duration=180,
        parameters={"memory_mb": 1024}
    ),
}
