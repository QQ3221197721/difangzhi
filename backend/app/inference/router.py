# 地方志数据智能管理系统 - 智能路由器
"""多模型智能路由、负载均衡、故障转移"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import defaultdict
import structlog

from .engine import InferenceEngine, InferenceConfig, InferenceResult, InferenceBackend

logger = structlog.get_logger()


class RoutingStrategy(str, Enum):
    """路由策略"""
    ROUND_ROBIN = "round_robin"      # 轮询
    WEIGHTED = "weighted"             # 加权
    LATENCY_BASED = "latency_based"   # 延迟优先
    COST_BASED = "cost_based"         # 成本优先
    QUALITY_BASED = "quality_based"   # 质量优先
    ADAPTIVE = "adaptive"             # 自适应


class TaskType(str, Enum):
    """任务类型"""
    CHAT = "chat"                     # 对话
    COMPLETION = "completion"         # 补全
    SUMMARIZATION = "summarization"   # 摘要
    TRANSLATION = "translation"       # 翻译
    EXTRACTION = "extraction"         # 信息抽取
    QA = "qa"                         # 问答
    ANALYSIS = "analysis"             # 分析
    CREATIVE = "creative"             # 创意写作


@dataclass
class ModelEndpoint:
    """模型端点"""
    id: str
    name: str
    backend: InferenceBackend
    config: InferenceConfig
    weight: float = 1.0
    cost_per_1k_tokens: float = 0.0
    max_tokens: int = 4096
    supported_tasks: List[TaskType] = field(default_factory=list)
    is_available: bool = True
    # 运行时统计
    total_requests: int = 0
    total_tokens: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    quality_score: float = 1.0
    
    def update_stats(self, latency_ms: float, tokens: int, success: bool):
        """更新统计"""
        self.total_requests += 1
        if success:
            self.total_tokens += tokens
            # 移动平均
            self.avg_latency_ms = 0.9 * self.avg_latency_ms + 0.1 * latency_ms
        else:
            self.total_errors += 1


@dataclass
class RouterConfig:
    """路由器配置"""
    strategy: RoutingStrategy = RoutingStrategy.ADAPTIVE
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 60.0
    fallback_enabled: bool = True
    health_check_interval: float = 60.0
    # 自适应权重
    latency_weight: float = 0.3
    cost_weight: float = 0.3
    quality_weight: float = 0.4


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, float] = {}
        self.open_circuits: set = set()
    
    def record_failure(self, endpoint_id: str):
        """记录失败"""
        self.failures[endpoint_id] += 1
        self.last_failure_time[endpoint_id] = time.time()
        
        if self.failures[endpoint_id] >= self.failure_threshold:
            self.open_circuits.add(endpoint_id)
            logger.warning("Circuit breaker opened", endpoint=endpoint_id)
    
    def record_success(self, endpoint_id: str):
        """记录成功"""
        self.failures[endpoint_id] = 0
        if endpoint_id in self.open_circuits:
            self.open_circuits.discard(endpoint_id)
            logger.info("Circuit breaker closed", endpoint=endpoint_id)
    
    def is_open(self, endpoint_id: str) -> bool:
        """检查熔断器状态"""
        if endpoint_id not in self.open_circuits:
            return False
        
        # 检查是否可以尝试恢复
        last_failure = self.last_failure_time.get(endpoint_id, 0)
        if time.time() - last_failure > self.recovery_timeout:
            return False  # 半开状态，允许尝试
        
        return True


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self):
        self._round_robin_index: Dict[str, int] = defaultdict(int)
    
    def select_round_robin(self, endpoints: List[ModelEndpoint]) -> Optional[ModelEndpoint]:
        """轮询选择"""
        if not endpoints:
            return None
        
        key = ",".join(e.id for e in endpoints)
        idx = self._round_robin_index[key] % len(endpoints)
        self._round_robin_index[key] += 1
        return endpoints[idx]
    
    def select_weighted(self, endpoints: List[ModelEndpoint]) -> Optional[ModelEndpoint]:
        """加权随机选择"""
        if not endpoints:
            return None
        
        total_weight = sum(e.weight for e in endpoints)
        if total_weight <= 0:
            return random.choice(endpoints)
        
        r = random.uniform(0, total_weight)
        cumulative = 0
        for endpoint in endpoints:
            cumulative += endpoint.weight
            if r <= cumulative:
                return endpoint
        
        return endpoints[-1]
    
    def select_latency_based(self, endpoints: List[ModelEndpoint]) -> Optional[ModelEndpoint]:
        """延迟优先选择"""
        if not endpoints:
            return None
        
        # 按平均延迟排序，选择最低的
        sorted_endpoints = sorted(endpoints, key=lambda e: e.avg_latency_ms)
        
        # 加入一些随机性，避免雪崩
        top_n = max(1, len(sorted_endpoints) // 3)
        return random.choice(sorted_endpoints[:top_n])
    
    def select_cost_based(self, endpoints: List[ModelEndpoint]) -> Optional[ModelEndpoint]:
        """成本优先选择"""
        if not endpoints:
            return None
        
        return min(endpoints, key=lambda e: e.cost_per_1k_tokens)
    
    def select_adaptive(
        self,
        endpoints: List[ModelEndpoint],
        latency_weight: float = 0.3,
        cost_weight: float = 0.3,
        quality_weight: float = 0.4
    ) -> Optional[ModelEndpoint]:
        """自适应选择"""
        if not endpoints:
            return None
        
        # 计算综合得分
        max_latency = max(e.avg_latency_ms for e in endpoints) or 1
        max_cost = max(e.cost_per_1k_tokens for e in endpoints) or 1
        
        scores = []
        for endpoint in endpoints:
            latency_score = 1 - (endpoint.avg_latency_ms / max_latency)
            cost_score = 1 - (endpoint.cost_per_1k_tokens / max_cost)
            quality_score = endpoint.quality_score
            
            total_score = (
                latency_weight * latency_score +
                cost_weight * cost_score +
                quality_weight * quality_score
            )
            scores.append((endpoint, total_score))
        
        # 按得分排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # 选择前几名中的一个
        top_n = max(1, len(scores) // 3)
        weights = [s[1] for s in scores[:top_n]]
        total = sum(weights)
        if total > 0:
            r = random.uniform(0, total)
            cumulative = 0
            for endpoint, score in scores[:top_n]:
                cumulative += score
                if r <= cumulative:
                    return endpoint
        
        return scores[0][0]


class SmartRouter:
    """智能路由器"""
    
    def __init__(self, config: RouterConfig = None):
        self.config = config or RouterConfig()
        self.endpoints: Dict[str, ModelEndpoint] = {}
        self.engines: Dict[str, InferenceEngine] = {}
        self.circuit_breaker = CircuitBreaker()
        self.load_balancer = LoadBalancer()
        self._initialized = False
        self._health_check_task: Optional[asyncio.Task] = None
        
        # 任务到模型的映射
        self.task_model_mapping: Dict[TaskType, List[str]] = defaultdict(list)
    
    def register_endpoint(
        self,
        endpoint: ModelEndpoint,
        engine_kwargs: Optional[Dict] = None
    ):
        """注册模型端点"""
        self.endpoints[endpoint.id] = endpoint
        
        # 创建推理引擎
        engine = InferenceEngine(endpoint.config, **(engine_kwargs or {}))
        self.engines[endpoint.id] = engine
        
        # 更新任务映射
        for task in endpoint.supported_tasks:
            if endpoint.id not in self.task_model_mapping[task]:
                self.task_model_mapping[task].append(endpoint.id)
        
        logger.info("Endpoint registered", endpoint=endpoint.id, name=endpoint.name)
    
    async def initialize(self) -> bool:
        """初始化所有引擎"""
        tasks = []
        for endpoint_id, engine in self.engines.items():
            tasks.append(self._init_engine(endpoint_id, engine))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        self._initialized = success_count > 0
        
        # 启动健康检查
        if self._initialized:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info(
            "Router initialized",
            total=len(self.endpoints),
            success=success_count
        )
        return self._initialized
    
    async def _init_engine(self, endpoint_id: str, engine: InferenceEngine) -> bool:
        """初始化单个引擎"""
        try:
            result = await engine.initialize()
            self.endpoints[endpoint_id].is_available = result
            return result
        except Exception as e:
            logger.error("Engine init failed", endpoint=endpoint_id, error=str(e))
            self.endpoints[endpoint_id].is_available = False
            return False
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            await asyncio.sleep(self.config.health_check_interval)
            await self._run_health_checks()
    
    async def _run_health_checks(self):
        """执行健康检查"""
        for endpoint_id, engine in self.engines.items():
            try:
                is_healthy = await engine.health_check()
                self.endpoints[endpoint_id].is_available = is_healthy
                
                if is_healthy:
                    self.circuit_breaker.record_success(endpoint_id)
                else:
                    self.circuit_breaker.record_failure(endpoint_id)
            except Exception:
                self.endpoints[endpoint_id].is_available = False
                self.circuit_breaker.record_failure(endpoint_id)
    
    def _get_available_endpoints(
        self,
        task_type: Optional[TaskType] = None
    ) -> List[ModelEndpoint]:
        """获取可用端点"""
        endpoints = []
        
        for endpoint_id, endpoint in self.endpoints.items():
            # 检查可用性
            if not endpoint.is_available:
                continue
            
            # 检查熔断器
            if self.circuit_breaker.is_open(endpoint_id):
                continue
            
            # 检查任务支持
            if task_type and endpoint.supported_tasks:
                if task_type not in endpoint.supported_tasks:
                    continue
            
            endpoints.append(endpoint)
        
        return endpoints
    
    def _select_endpoint(
        self,
        endpoints: List[ModelEndpoint]
    ) -> Optional[ModelEndpoint]:
        """选择端点"""
        if not endpoints:
            return None
        
        strategy = self.config.strategy
        
        if strategy == RoutingStrategy.ROUND_ROBIN:
            return self.load_balancer.select_round_robin(endpoints)
        elif strategy == RoutingStrategy.WEIGHTED:
            return self.load_balancer.select_weighted(endpoints)
        elif strategy == RoutingStrategy.LATENCY_BASED:
            return self.load_balancer.select_latency_based(endpoints)
        elif strategy == RoutingStrategy.COST_BASED:
            return self.load_balancer.select_cost_based(endpoints)
        elif strategy == RoutingStrategy.ADAPTIVE:
            return self.load_balancer.select_adaptive(
                endpoints,
                self.config.latency_weight,
                self.config.cost_weight,
                self.config.quality_weight
            )
        else:
            return random.choice(endpoints)
    
    async def route(
        self,
        prompt: str,
        task_type: Optional[TaskType] = None,
        preferred_endpoint: Optional[str] = None,
        **kwargs
    ) -> InferenceResult:
        """智能路由请求"""
        if not self._initialized:
            await self.initialize()
        
        # 获取可用端点
        available = self._get_available_endpoints(task_type)
        
        if not available:
            raise RuntimeError("No available endpoints")
        
        # 优先使用指定端点
        if preferred_endpoint and preferred_endpoint in self.endpoints:
            endpoint = self.endpoints[preferred_endpoint]
            if endpoint in available:
                available = [endpoint]
        
        # 重试逻辑
        last_error = None
        tried_endpoints = set()
        
        for attempt in range(self.config.max_retries):
            # 选择端点
            remaining = [e for e in available if e.id not in tried_endpoints]
            if not remaining:
                remaining = available  # 重试所有
            
            endpoint = self._select_endpoint(remaining)
            if not endpoint:
                break
            
            tried_endpoints.add(endpoint.id)
            
            try:
                result = await self._execute_with_endpoint(endpoint, prompt, **kwargs)
                
                # 记录成功
                self.circuit_breaker.record_success(endpoint.id)
                endpoint.update_stats(result.latency_ms, result.tokens_used, True)
                
                return result
                
            except asyncio.TimeoutError:
                logger.warning(
                    "Request timeout",
                    endpoint=endpoint.id,
                    attempt=attempt + 1
                )
                self.circuit_breaker.record_failure(endpoint.id)
                endpoint.update_stats(self.config.timeout * 1000, 0, False)
                last_error = TimeoutError(f"Timeout on endpoint {endpoint.id}")
                
            except Exception as e:
                logger.warning(
                    "Request failed",
                    endpoint=endpoint.id,
                    attempt=attempt + 1,
                    error=str(e)
                )
                self.circuit_breaker.record_failure(endpoint.id)
                endpoint.update_stats(0, 0, False)
                last_error = e
            
            # 重试延迟
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        raise last_error or RuntimeError("All endpoints failed")
    
    async def _execute_with_endpoint(
        self,
        endpoint: ModelEndpoint,
        prompt: str,
        **kwargs
    ) -> InferenceResult:
        """在指定端点执行"""
        engine = self.engines[endpoint.id]
        
        return await asyncio.wait_for(
            engine.generate(prompt, **kwargs),
            timeout=self.config.timeout
        )
    
    async def stream_route(
        self,
        prompt: str,
        task_type: Optional[TaskType] = None,
        preferred_endpoint: Optional[str] = None,
        **kwargs
    ):
        """流式路由"""
        if not self._initialized:
            await self.initialize()
        
        available = self._get_available_endpoints(task_type)
        if not available:
            raise RuntimeError("No available endpoints")
        
        endpoint = self._select_endpoint(available)
        if not endpoint:
            raise RuntimeError("Failed to select endpoint")
        
        engine = self.engines[endpoint.id]
        
        async for chunk in engine.stream_generate(prompt, **kwargs):
            yield chunk
    
    def get_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        stats = {
            "total_endpoints": len(self.endpoints),
            "available_endpoints": len(self._get_available_endpoints()),
            "endpoints": {}
        }
        
        for endpoint_id, endpoint in self.endpoints.items():
            stats["endpoints"][endpoint_id] = {
                "name": endpoint.name,
                "is_available": endpoint.is_available,
                "total_requests": endpoint.total_requests,
                "total_tokens": endpoint.total_tokens,
                "total_errors": endpoint.total_errors,
                "avg_latency_ms": round(endpoint.avg_latency_ms, 2),
                "quality_score": endpoint.quality_score,
                "circuit_open": self.circuit_breaker.is_open(endpoint_id)
            }
        
        return stats
    
    async def shutdown(self):
        """关闭路由器"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Router shutdown")


# 预设端点配置
def create_default_endpoints() -> List[Tuple[ModelEndpoint, Dict]]:
    """创建默认端点配置"""
    endpoints = []
    
    # OpenAI GPT-4
    endpoints.append((
        ModelEndpoint(
            id="openai-gpt4",
            name="GPT-4",
            backend=InferenceBackend.OPENAI,
            config=InferenceConfig(
                backend=InferenceBackend.OPENAI,
                model_name="gpt-4",
                max_tokens=4096
            ),
            weight=1.0,
            cost_per_1k_tokens=0.03,
            max_tokens=8192,
            supported_tasks=[
                TaskType.CHAT, TaskType.QA, TaskType.ANALYSIS,
                TaskType.CREATIVE, TaskType.SUMMARIZATION
            ]
        ),
        {"api_key": ""}
    ))
    
    # OpenAI GPT-3.5
    endpoints.append((
        ModelEndpoint(
            id="openai-gpt35",
            name="GPT-3.5-Turbo",
            backend=InferenceBackend.OPENAI,
            config=InferenceConfig(
                backend=InferenceBackend.OPENAI,
                model_name="gpt-3.5-turbo",
                max_tokens=4096
            ),
            weight=2.0,  # 更高权重
            cost_per_1k_tokens=0.002,
            max_tokens=4096,
            supported_tasks=[
                TaskType.CHAT, TaskType.QA, TaskType.COMPLETION,
                TaskType.TRANSLATION, TaskType.EXTRACTION
            ]
        ),
        {"api_key": ""}
    ))
    
    # Ollama 本地模型
    endpoints.append((
        ModelEndpoint(
            id="ollama-qwen",
            name="Qwen2-7B (Local)",
            backend=InferenceBackend.OLLAMA,
            config=InferenceConfig(
                backend=InferenceBackend.OLLAMA,
                model_name="qwen2:7b",
                max_tokens=4096
            ),
            weight=1.5,
            cost_per_1k_tokens=0.0,  # 本地免费
            max_tokens=4096,
            supported_tasks=[
                TaskType.CHAT, TaskType.QA, TaskType.COMPLETION,
                TaskType.SUMMARIZATION
            ]
        ),
        {"base_url": "http://localhost:11434"}
    ))
    
    return endpoints
