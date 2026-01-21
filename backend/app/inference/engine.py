# 地方志数据智能管理系统 - 推理引擎
"""支持多后端的统一推理接口"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import time
import structlog

logger = structlog.get_logger()


class InferenceBackend(str, Enum):
    """推理后端类型"""
    OPENAI = "openai"
    LOCAL_LLM = "local_llm"
    OLLAMA = "ollama"
    VLLM = "vllm"


@dataclass
class InferenceConfig:
    """推理配置"""
    backend: InferenceBackend = InferenceBackend.OPENAI
    model_name: str = "gpt-3.5-turbo"
    max_tokens: int = 2000
    temperature: float = 0.7
    top_p: float = 1.0
    timeout: float = 60.0
    retry_count: int = 3
    # 本地模型配置
    local_model_path: Optional[str] = None
    device: str = "cpu"  # cpu/cuda/mps
    quantization: Optional[str] = None  # 4bit/8bit/none


@dataclass
class InferenceResult:
    """推理结果"""
    content: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    model_name: str = ""
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseInferenceEngine(ABC):
    """推理引擎基类"""
    
    def __init__(self, config: InferenceConfig):
        self.config = config
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化引擎"""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> InferenceResult:
        """生成文本"""
        pass
    
    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ):
        """流式生成"""
        pass
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            result = await self.generate("Hello", max_tokens=5)
            return len(result.content) > 0
        except Exception:
            return False


class OpenAIEngine(BaseInferenceEngine):
    """OpenAI 推理引擎"""
    
    def __init__(self, config: InferenceConfig, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.client = None
    
    async def initialize(self) -> bool:
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
            self._initialized = True
            logger.info("OpenAI engine initialized", model=self.config.model_name)
            return True
        except Exception as e:
            logger.error("OpenAI engine init failed", error=str(e))
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> InferenceResult:
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        temperature = kwargs.get("temperature", self.config.temperature)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=self.config.top_p,
            )
            
            latency = (time.time() - start_time) * 1000
            
            return InferenceResult(
                content=response.choices[0].message.content,
                tokens_used=response.usage.total_tokens,
                latency_ms=latency,
                model_name=self.config.model_name,
                finish_reason=response.choices[0].finish_reason,
            )
        except Exception as e:
            logger.error("OpenAI generate failed", error=str(e))
            raise
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ):
        if not self._initialized:
            await self.initialize()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        stream = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OllamaEngine(BaseInferenceEngine):
    """Ollama 本地推理引擎"""
    
    def __init__(self, config: InferenceConfig, base_url: str = "http://localhost:11434"):
        super().__init__(config)
        self.base_url = base_url
        self.session = None
    
    async def initialize(self) -> bool:
        try:
            import aiohttp
            self.session = aiohttp.ClientSession()
            
            # 检查模型是否可用
            async with self.session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    if self.config.model_name not in models:
                        logger.warning(f"Model {self.config.model_name} not found, available: {models}")
            
            self._initialized = True
            logger.info("Ollama engine initialized", model=self.config.model_name)
            return True
        except Exception as e:
            logger.error("Ollama engine init failed", error=str(e))
            return False
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> InferenceResult:
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        full_prompt = ""
        if system_prompt:
            full_prompt += f"System: {system_prompt}\n\n"
        if history:
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                full_prompt += f"{role}: {msg['content']}\n\n"
        full_prompt += f"User: {prompt}\n\nAssistant:"
        
        payload = {
            "model": self.config.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            }
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as resp:
                data = await resp.json()
                latency = (time.time() - start_time) * 1000
                
                return InferenceResult(
                    content=data.get("response", ""),
                    tokens_used=data.get("eval_count", 0),
                    latency_ms=latency,
                    model_name=self.config.model_name,
                    finish_reason="stop",
                )
        except Exception as e:
            logger.error("Ollama generate failed", error=str(e))
            raise
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ):
        if not self._initialized:
            await self.initialize()
        
        full_prompt = ""
        if system_prompt:
            full_prompt += f"System: {system_prompt}\n\n"
        full_prompt += f"User: {prompt}\n\nAssistant:"
        
        payload = {
            "model": self.config.model_name,
            "prompt": full_prompt,
            "stream": True,
        }
        
        async with self.session.post(
            f"{self.base_url}/api/generate",
            json=payload
        ) as resp:
            async for line in resp.content:
                if line:
                    import json
                    data = json.loads(line)
                    if data.get("response"):
                        yield data["response"]


class InferenceEngine:
    """统一推理引擎入口"""
    
    def __init__(self, config: InferenceConfig, **kwargs):
        self.config = config
        self.engine: Optional[BaseInferenceEngine] = None
        self.kwargs = kwargs
    
    async def initialize(self) -> bool:
        """初始化推理引擎"""
        if self.config.backend == InferenceBackend.OPENAI:
            api_key = self.kwargs.get("api_key", "")
            self.engine = OpenAIEngine(self.config, api_key)
        elif self.config.backend == InferenceBackend.OLLAMA:
            base_url = self.kwargs.get("base_url", "http://localhost:11434")
            self.engine = OllamaEngine(self.config, base_url)
        else:
            raise ValueError(f"Unsupported backend: {self.config.backend}")
        
        return await self.engine.initialize()
    
    async def generate(self, prompt: str, **kwargs) -> InferenceResult:
        """生成文本"""
        if not self.engine:
            await self.initialize()
        return await self.engine.generate(prompt, **kwargs)
    
    async def stream_generate(self, prompt: str, **kwargs):
        """流式生成"""
        if not self.engine:
            await self.initialize()
        async for chunk in self.engine.stream_generate(prompt, **kwargs):
            yield chunk
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not self.engine:
            return False
        return await self.engine.health_check()
