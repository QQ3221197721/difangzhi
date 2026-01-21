# 地方志数据智能管理系统 - RAG管道
"""检索增强生成（Retrieval-Augmented Generation）"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import asyncio
import structlog

from .engine import InferenceEngine, InferenceConfig, InferenceBackend
from .embedding import EmbeddingService, EmbeddingConfig, EmbeddingBackend
from .vector_store import VectorStore, FAISSVectorStore, VectorSearchResult

logger = structlog.get_logger()


@dataclass
class RAGConfig:
    """RAG配置"""
    # 检索配置
    top_k: int = 5
    min_score: float = 0.5
    rerank: bool = False
    
    # 生成配置
    max_context_length: int = 4000
    temperature: float = 0.7
    
    # 提示模板
    system_prompt: str = """你是一个专业的地方志资料助手。请基于提供的参考资料回答用户问题。
如果资料中没有相关信息，请明确告知用户。回答时请引用资料来源。"""
    
    context_template: str = """参考资料：
{context}

用户问题：{question}

请基于以上资料提供准确的回答："""


@dataclass
class RetrievalResult:
    """检索结果"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResponse:
    """RAG响应"""
    answer: str
    sources: List[RetrievalResult]
    confidence: float
    tokens_used: int = 0


class RAGPipeline:
    """RAG管道"""
    
    def __init__(
        self,
        config: RAGConfig,
        inference_engine: InferenceEngine,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        self.config = config
        self.inference = inference_engine
        self.embedding = embedding_service
        self.vector_store = vector_store
        self._initialized = False
    
    async def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            results = await asyncio.gather(
                self.inference.initialize(),
                self.vector_store.initialize(),
                return_exceptions=True
            )
            
            self._initialized = all(r is True for r in results if not isinstance(r, Exception))
            
            if self._initialized:
                logger.info("RAG pipeline initialized")
            else:
                logger.error("RAG pipeline init failed", results=results)
            
            return self._initialized
        except Exception as e:
            logger.error("RAG pipeline init error", error=str(e))
            return False
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        id_field: str = "id",
        content_field: str = "content"
    ) -> int:
        """添加文档到向量库"""
        if not self._initialized:
            await self.initialize()
        
        ids = []
        contents = []
        metadata_list = []
        
        for doc in documents:
            doc_id = str(doc.get(id_field, ""))
            content = doc.get(content_field, "")
            
            if not doc_id or not content:
                continue
            
            ids.append(doc_id)
            contents.append(content)
            metadata_list.append({
                k: v for k, v in doc.items()
                if k not in [content_field] and isinstance(v, (str, int, float, bool))
            })
        
        if not ids:
            return 0
        
        # 批量生成嵌入
        embeddings = await self.embedding.embed_batch(contents)
        
        # 添加到向量库
        await self.vector_store.add(ids, embeddings, metadata_list)
        
        logger.info("Documents added to RAG", count=len(ids))
        return len(ids)
    
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """检索相关文档"""
        if not self._initialized:
            await self.initialize()
        
        top_k = top_k or self.config.top_k
        
        # 生成查询嵌入
        query_embedding = await self.embedding.embed(query)
        
        # 向量搜索
        search_results = await self.vector_store.search(
            query_embedding,
            top_k=top_k * 2,  # 多检索一些用于过滤
            filter=filter
        )
        
        # 过滤低分结果
        results = []
        for sr in search_results:
            if sr.score >= self.config.min_score:
                results.append(RetrievalResult(
                    id=sr.id,
                    content=sr.metadata.get("content", ""),
                    score=sr.score,
                    metadata=sr.metadata
                ))
        
        return results[:top_k]
    
    async def generate(
        self,
        query: str,
        context: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """生成回答"""
        prompt = self.config.context_template.format(
            context=context,
            question=query
        )
        
        result = await self.inference.generate(
            prompt,
            system_prompt=self.config.system_prompt,
            history=history,
            temperature=self.config.temperature
        )
        
        return result.content
    
    async def query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        filter: Optional[Dict] = None
    ) -> RAGResponse:
        """完整RAG查询流程"""
        if not self._initialized:
            await self.initialize()
        
        # 1. 检索相关文档
        retrieved = await self.retrieve(question, filter=filter)
        
        if not retrieved:
            return RAGResponse(
                answer="抱歉，未找到相关资料来回答您的问题。",
                sources=[],
                confidence=0.0
            )
        
        # 2. 构建上下文
        context_parts = []
        total_length = 0
        selected = []
        
        for doc in retrieved:
            doc_text = f"【{doc.metadata.get('title', doc.id)}】\n{doc.content}"
            if total_length + len(doc_text) > self.config.max_context_length:
                break
            context_parts.append(doc_text)
            total_length += len(doc_text)
            selected.append(doc)
        
        context = "\n\n".join(context_parts)
        
        # 3. 生成回答
        answer = await self.generate(question, context, history)
        
        # 4. 计算置信度
        avg_score = sum(d.score for d in selected) / len(selected) if selected else 0
        confidence = min(avg_score, 1.0)
        
        return RAGResponse(
            answer=answer,
            sources=selected,
            confidence=confidence
        )
    
    async def stream_query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        filter: Optional[Dict] = None
    ):
        """流式RAG查询"""
        if not self._initialized:
            await self.initialize()
        
        # 检索
        retrieved = await self.retrieve(question, filter=filter)
        
        if not retrieved:
            yield "抱歉，未找到相关资料来回答您的问题。"
            return
        
        # 构建上下文
        context_parts = []
        for doc in retrieved[:self.config.top_k]:
            context_parts.append(f"【{doc.metadata.get('title', doc.id)}】\n{doc.content}")
        context = "\n\n".join(context_parts)
        
        # 流式生成
        prompt = self.config.context_template.format(
            context=context,
            question=question
        )
        
        async for chunk in self.inference.stream_generate(
            prompt,
            system_prompt=self.config.system_prompt,
            history=history
        ):
            yield chunk


async def create_rag_pipeline(
    inference_backend: InferenceBackend = InferenceBackend.OPENAI,
    embedding_backend: EmbeddingBackend = EmbeddingBackend.SENTENCE_TRANSFORMERS,
    **kwargs
) -> RAGPipeline:
    """创建RAG管道的工厂函数"""
    
    # 推理配置
    inference_config = InferenceConfig(
        backend=inference_backend,
        model_name=kwargs.get("llm_model", "gpt-3.5-turbo"),
        temperature=kwargs.get("temperature", 0.7)
    )
    
    # 嵌入配置
    embedding_config = EmbeddingConfig(
        backend=embedding_backend,
        model_name=kwargs.get("embedding_model", "paraphrase-multilingual-MiniLM-L12-v2"),
        dimension=kwargs.get("embedding_dim", 384)
    )
    
    # RAG配置
    rag_config = RAGConfig(
        top_k=kwargs.get("top_k", 5),
        min_score=kwargs.get("min_score", 0.5)
    )
    
    # 创建组件
    inference_engine = InferenceEngine(
        inference_config,
        api_key=kwargs.get("openai_api_key", "")
    )
    
    embedding_service = EmbeddingService(
        embedding_config,
        api_key=kwargs.get("openai_api_key", "")
    )
    
    vector_store = FAISSVectorStore(
        dimension=embedding_config.dimension,
        index_path=kwargs.get("vector_path", "vectors/faiss")
    )
    
    pipeline = RAGPipeline(
        rag_config,
        inference_engine,
        embedding_service,
        vector_store
    )
    
    await pipeline.initialize()
    
    return pipeline
