# 地方志数据智能管理系统 - 嵌入服务
"""文本向量化服务，支持本地和远程模型"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union
import numpy as np
import structlog

logger = structlog.get_logger()


class EmbeddingBackend(str, Enum):
    """嵌入后端类型"""
    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    HUGGINGFACE = "huggingface"


@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    backend: EmbeddingBackend = EmbeddingBackend.SENTENCE_TRANSFORMERS
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    dimension: int = 384
    max_length: int = 512
    batch_size: int = 32
    device: str = "cpu"
    normalize: bool = True


class BaseEmbedding(ABC):
    """嵌入服务基类"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化"""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """单文本嵌入"""
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入"""
        pass
    
    def normalize_vector(self, vec: List[float]) -> List[float]:
        """L2归一化"""
        arr = np.array(vec)
        norm = np.linalg.norm(arr)
        if norm > 0:
            return (arr / norm).tolist()
        return vec


class LocalEmbedding(BaseEmbedding):
    """本地Sentence-Transformers嵌入"""
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.model = None
    
    async def initialize(self) -> bool:
        try:
            from sentence_transformers import SentenceTransformer
            
            self.model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device
            )
            self._initialized = True
            logger.info(
                "Local embedding initialized",
                model=self.config.model_name,
                device=self.config.device
            )
            return True
        except Exception as e:
            logger.error("Local embedding init failed", error=str(e))
            return False
    
    async def embed(self, text: str) -> List[float]:
        if not self._initialized:
            await self.initialize()
        
        # 截断文本
        if len(text) > self.config.max_length * 4:
            text = text[:self.config.max_length * 4]
        
        # 在线程池中执行
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode(text, convert_to_numpy=True)
        )
        
        vec = embedding.tolist()
        if self.config.normalize:
            vec = self.normalize_vector(vec)
        
        return vec
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._initialized:
            await self.initialize()
        
        # 截断文本
        texts = [t[:self.config.max_length * 4] for t in texts]
        
        # 批量处理
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(
                texts,
                batch_size=self.config.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )
        )
        
        results = []
        for emb in embeddings:
            vec = emb.tolist()
            if self.config.normalize:
                vec = self.normalize_vector(vec)
            results.append(vec)
        
        return results


class OpenAIEmbedding(BaseEmbedding):
    """OpenAI嵌入服务"""
    
    def __init__(self, config: EmbeddingConfig, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.client = None
    
    async def initialize(self) -> bool:
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
            self._initialized = True
            logger.info("OpenAI embedding initialized", model=self.config.model_name)
            return True
        except Exception as e:
            logger.error("OpenAI embedding init failed", error=str(e))
            return False
    
    async def embed(self, text: str) -> List[float]:
        if not self._initialized:
            await self.initialize()
        
        # 截断
        if len(text) > 8000:
            text = text[:8000]
        
        response = await self.client.embeddings.create(
            model=self.config.model_name,
            input=text
        )
        
        vec = response.data[0].embedding
        if self.config.normalize:
            vec = self.normalize_vector(vec)
        
        return vec
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._initialized:
            await self.initialize()
        
        # 截断
        texts = [t[:8000] for t in texts]
        
        response = await self.client.embeddings.create(
            model=self.config.model_name,
            input=texts
        )
        
        results = []
        for item in response.data:
            vec = item.embedding
            if self.config.normalize:
                vec = self.normalize_vector(vec)
            results.append(vec)
        
        return results


class HuggingFaceEmbedding(BaseEmbedding):
    """HuggingFace模型嵌入"""
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.model = None
        self.tokenizer = None
    
    async def initialize(self) -> bool:
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            self.model = AutoModel.from_pretrained(self.config.model_name)
            
            if self.config.device == "cuda" and torch.cuda.is_available():
                self.model = self.model.cuda()
            
            self.model.eval()
            self._initialized = True
            logger.info("HuggingFace embedding initialized", model=self.config.model_name)
            return True
        except Exception as e:
            logger.error("HuggingFace embedding init failed", error=str(e))
            return False
    
    async def embed(self, text: str) -> List[float]:
        if not self._initialized:
            await self.initialize()
        
        import torch
        
        loop = asyncio.get_event_loop()
        
        def _encode():
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                max_length=self.config.max_length,
                truncation=True,
                padding=True
            )
            
            if self.config.device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Mean pooling
                embeddings = outputs.last_hidden_state.mean(dim=1)
            
            return embeddings[0].cpu().numpy().tolist()
        
        vec = await loop.run_in_executor(None, _encode)
        
        if self.config.normalize:
            vec = self.normalize_vector(vec)
        
        return vec
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # 简单实现：逐个处理
        results = []
        for text in texts:
            vec = await self.embed(text)
            results.append(vec)
        return results


class EmbeddingService:
    """嵌入服务统一入口"""
    
    def __init__(self, config: EmbeddingConfig, **kwargs):
        self.config = config
        self.kwargs = kwargs
        self.engine: Optional[BaseEmbedding] = None
    
    async def initialize(self) -> bool:
        if self.config.backend == EmbeddingBackend.SENTENCE_TRANSFORMERS:
            self.engine = LocalEmbedding(self.config)
        elif self.config.backend == EmbeddingBackend.OPENAI:
            api_key = self.kwargs.get("api_key", "")
            self.engine = OpenAIEmbedding(self.config, api_key)
        elif self.config.backend == EmbeddingBackend.HUGGINGFACE:
            self.engine = HuggingFaceEmbedding(self.config)
        else:
            raise ValueError(f"Unsupported backend: {self.config.backend}")
        
        return await self.engine.initialize()
    
    async def embed(self, text: str) -> List[float]:
        if not self.engine:
            await self.initialize()
        return await self.engine.embed(text)
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self.engine:
            await self.initialize()
        return await self.engine.embed_batch(texts)
    
    @property
    def dimension(self) -> int:
        return self.config.dimension
