# 地方志数据智能管理系统 - 高级RAG
"""混合检索、查询扩展、多阶段重排序、HyDE增强"""

import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import structlog

from .engine import InferenceEngine, InferenceConfig, InferenceResult
from .embedding import EmbeddingService, EmbeddingConfig
from .vector_store import VectorStore, VectorSearchResult

logger = structlog.get_logger()


class RetrievalStrategy(str, Enum):
    """检索策略"""
    DENSE = "dense"                   # 稠密向量检索
    SPARSE = "sparse"                 # 稀疏检索(BM25)
    HYBRID = "hybrid"                 # 混合检索
    MULTI_QUERY = "multi_query"       # 多查询检索
    HYDE = "hyde"                     # 假设文档嵌入


class RerankStrategy(str, Enum):
    """重排序策略"""
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"   # 交叉编码器
    LLM_BASED = "llm_based"           # LLM评分
    RECIPROCAL_RANK = "reciprocal_rank"  # 倒数排名融合


@dataclass
class AdvancedRAGConfig:
    """高级RAG配置"""
    # 检索配置
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    top_k: int = 10
    min_score: float = 0.3
    
    # 查询扩展
    query_expansion_enabled: bool = True
    expansion_count: int = 3
    
    # 重排序
    rerank_strategy: RerankStrategy = RerankStrategy.RECIPROCAL_RANK
    rerank_top_k: int = 5
    
    # HyDE
    hyde_enabled: bool = False
    hyde_prompt_template: str = """请根据以下问题，生成一段可能包含答案的假设性文档段落。
问题：{question}
假设文档："""
    
    # 上下文配置
    max_context_length: int = 4000
    chunk_overlap: int = 50
    
    # 答案生成
    temperature: float = 0.3
    citation_enabled: bool = True


@dataclass
class RetrievedChunk:
    """检索到的文档块"""
    id: str
    content: str
    score: float
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_explanation: str = ""
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class RAGContext:
    """RAG上下文"""
    chunks: List[RetrievedChunk]
    total_tokens: int = 0
    retrieval_strategy: str = ""
    query_variants: List[str] = field(default_factory=list)


@dataclass
class AdvancedRAGResponse:
    """高级RAG响应"""
    answer: str
    context: RAGContext
    confidence: float
    citations: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    tokens_used: int = 0


class BM25Retriever:
    """BM25稀疏检索器"""
    
    def __init__(self):
        self.documents: Dict[str, str] = {}
        self.doc_metadata: Dict[str, Dict] = {}
        self._bm25 = None
        self._corpus = []
        self._doc_ids = []
    
    def add_documents(
        self,
        ids: List[str],
        contents: List[str],
        metadata: Optional[List[Dict]] = None
    ):
        """添加文档"""
        for i, (doc_id, content) in enumerate(zip(ids, contents)):
            self.documents[doc_id] = content
            if metadata and i < len(metadata):
                self.doc_metadata[doc_id] = metadata[i]
        
        self._build_index()
    
    def _build_index(self):
        """构建BM25索引"""
        try:
            from rank_bm25 import BM25Okapi
            import jieba
            
            self._doc_ids = list(self.documents.keys())
            self._corpus = []
            
            for doc_id in self._doc_ids:
                content = self.documents[doc_id]
                # 中文分词
                tokens = list(jieba.cut(content))
                self._corpus.append(tokens)
            
            self._bm25 = BM25Okapi(self._corpus)
            logger.info("BM25 index built", doc_count=len(self._doc_ids))
        except ImportError:
            logger.warning("rank_bm25 not installed, BM25 disabled")
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """搜索"""
        if not self._bm25:
            return []
        
        try:
            import jieba
            query_tokens = list(jieba.cut(query))
            scores = self._bm25.get_scores(query_tokens)
            
            # 获取top_k
            top_indices = np.argsort(scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                if scores[idx] > 0:
                    doc_id = self._doc_ids[idx]
                    # 归一化分数到0-1
                    normalized_score = min(scores[idx] / 20, 1.0)
                    results.append((doc_id, normalized_score))
            
            return results
        except Exception as e:
            logger.error("BM25 search failed", error=str(e))
            return []


class QueryExpander:
    """查询扩展器"""
    
    def __init__(self, inference_engine: InferenceEngine):
        self.engine = inference_engine
    
    async def expand(self, query: str, count: int = 3) -> List[str]:
        """扩展查询"""
        prompt = f"""请为以下查询生成{count}个语义相似但表达不同的查询变体，用于扩展检索范围。
每个变体单独一行，只输出变体，不要编号和解释。

原始查询：{query}

查询变体："""
        
        try:
            result = await self.engine.generate(prompt, max_tokens=200, temperature=0.7)
            variants = [v.strip() for v in result.content.strip().split('\n') if v.strip()]
            return variants[:count]
        except Exception as e:
            logger.error("Query expansion failed", error=str(e))
            return []


class HyDEGenerator:
    """HyDE假设文档生成器"""
    
    def __init__(self, inference_engine: InferenceEngine, prompt_template: str):
        self.engine = inference_engine
        self.prompt_template = prompt_template
    
    async def generate_hypothetical_document(self, query: str) -> str:
        """生成假设文档"""
        prompt = self.prompt_template.format(question=query)
        
        try:
            result = await self.engine.generate(prompt, max_tokens=300, temperature=0.5)
            return result.content.strip()
        except Exception as e:
            logger.error("HyDE generation failed", error=str(e))
            return query


class Reranker:
    """重排序器"""
    
    def __init__(
        self,
        strategy: RerankStrategy,
        inference_engine: Optional[InferenceEngine] = None
    ):
        self.strategy = strategy
        self.engine = inference_engine
        self._cross_encoder = None
    
    def _load_cross_encoder(self):
        """加载交叉编码器"""
        if self._cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            except ImportError:
                logger.warning("CrossEncoder not available")
    
    async def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        """重排序"""
        if not chunks:
            return []
        
        if self.strategy == RerankStrategy.NONE:
            return chunks[:top_k]
        
        elif self.strategy == RerankStrategy.CROSS_ENCODER:
            return await self._rerank_cross_encoder(query, chunks, top_k)
        
        elif self.strategy == RerankStrategy.LLM_BASED:
            return await self._rerank_llm(query, chunks, top_k)
        
        elif self.strategy == RerankStrategy.RECIPROCAL_RANK:
            # RRF已在混合检索中处理
            return chunks[:top_k]
        
        return chunks[:top_k]
    
    async def _rerank_cross_encoder(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int
    ) -> List[RetrievedChunk]:
        """交叉编码器重排序"""
        self._load_cross_encoder()
        
        if not self._cross_encoder:
            return chunks[:top_k]
        
        pairs = [(query, chunk.content) for chunk in chunks]
        
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: self._cross_encoder.predict(pairs)
        )
        
        # 更新分数并排序
        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)
        
        sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
        return sorted_chunks[:top_k]
    
    async def _rerank_llm(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int
    ) -> List[RetrievedChunk]:
        """LLM重排序"""
        if not self.engine:
            return chunks[:top_k]
        
        # 批量评分
        prompt = f"""请评估以下文档段落与查询的相关性，为每个段落打分(0-10分)。
只输出分数，每行一个，与段落顺序对应。

查询：{query}

段落：
"""
        for i, chunk in enumerate(chunks[:10]):  # 限制数量
            prompt += f"\n[{i+1}] {chunk.content[:200]}...\n"
        
        prompt += "\n分数(每行一个)："
        
        try:
            result = await self.engine.generate(prompt, max_tokens=100, temperature=0)
            scores = []
            for line in result.content.strip().split('\n'):
                try:
                    score = float(re.search(r'[\d.]+', line).group())
                    scores.append(min(score / 10, 1.0))
                except:
                    scores.append(0.5)
            
            # 更新分数
            for i, chunk in enumerate(chunks[:len(scores)]):
                chunk.score = scores[i]
            
            sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
            return sorted_chunks[:top_k]
        except Exception as e:
            logger.error("LLM rerank failed", error=str(e))
            return chunks[:top_k]


class AdvancedRAGPipeline:
    """高级RAG管道"""
    
    def __init__(
        self,
        config: AdvancedRAGConfig,
        inference_engine: InferenceEngine,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        self.config = config
        self.inference = inference_engine
        self.embedding = embedding_service
        self.vector_store = vector_store
        
        # 组件
        self.bm25 = BM25Retriever()
        self.query_expander = QueryExpander(inference_engine) if config.query_expansion_enabled else None
        self.hyde_generator = HyDEGenerator(inference_engine, config.hyde_prompt_template) if config.hyde_enabled else None
        self.reranker = Reranker(config.rerank_strategy, inference_engine)
        
        self._initialized = False
    
    async def initialize(self) -> bool:
        """初始化"""
        try:
            await asyncio.gather(
                self.inference.initialize(),
                self.vector_store.initialize()
            )
            self._initialized = True
            return True
        except Exception as e:
            logger.error("Advanced RAG init failed", error=str(e))
            return False
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        id_field: str = "id",
        content_field: str = "content"
    ) -> int:
        """添加文档"""
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
        
        # 向量索引
        embeddings = await self.embedding.embed_batch(contents)
        await self.vector_store.add(ids, embeddings, metadata_list)
        
        # BM25索引
        self.bm25.add_documents(ids, contents, metadata_list)
        
        return len(ids)
    
    async def _dense_retrieve(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedChunk]:
        """稠密向量检索"""
        query_embedding = await self.embedding.embed(query)
        results = await self.vector_store.search(query_embedding, top_k=top_k)
        
        chunks = []
        for r in results:
            chunks.append(RetrievedChunk(
                id=r.id,
                content=r.metadata.get("content", ""),
                score=r.score,
                source="dense",
                metadata=r.metadata
            ))
        return chunks
    
    async def _sparse_retrieve(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedChunk]:
        """稀疏BM25检索"""
        results = self.bm25.search(query, top_k=top_k)
        
        chunks = []
        for doc_id, score in results:
            content = self.bm25.documents.get(doc_id, "")
            metadata = self.bm25.doc_metadata.get(doc_id, {})
            chunks.append(RetrievedChunk(
                id=doc_id,
                content=content,
                score=score,
                source="sparse",
                metadata=metadata
            ))
        return chunks
    
    async def _hybrid_retrieve(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedChunk]:
        """混合检索"""
        # 并行检索
        dense_task = self._dense_retrieve(query, top_k * 2)
        sparse_task = self._sparse_retrieve(query, top_k * 2)
        
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
        
        # 倒数排名融合 (RRF)
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, RetrievedChunk] = {}
        
        k = 60  # RRF参数
        
        # Dense结果
        for rank, chunk in enumerate(dense_results):
            rrf_score = self.config.dense_weight / (k + rank + 1)
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + rrf_score
            chunk_map[chunk.id] = chunk
        
        # Sparse结果
        for rank, chunk in enumerate(sparse_results):
            rrf_score = self.config.sparse_weight / (k + rank + 1)
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + rrf_score
            if chunk.id not in chunk_map:
                chunk_map[chunk.id] = chunk
        
        # 按RRF分数排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        results = []
        for doc_id in sorted_ids[:top_k]:
            chunk = chunk_map[doc_id]
            chunk.score = rrf_scores[doc_id]
            chunk.source = "hybrid"
            results.append(chunk)
        
        return results
    
    async def _multi_query_retrieve(
        self,
        query: str,
        top_k: int
    ) -> Tuple[List[RetrievedChunk], List[str]]:
        """多查询检索"""
        # 扩展查询
        variants = [query]
        if self.query_expander:
            expanded = await self.query_expander.expand(query, self.config.expansion_count)
            variants.extend(expanded)
        
        # 并行检索所有变体
        tasks = [self._hybrid_retrieve(v, top_k) for v in variants]
        all_results = await asyncio.gather(*tasks)
        
        # 合并结果（RRF）
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, RetrievedChunk] = {}
        
        for query_rank, results in enumerate(all_results):
            weight = 1.0 if query_rank == 0 else 0.8  # 原始查询权重更高
            for rank, chunk in enumerate(results):
                rrf_score = weight / (60 + rank + 1)
                rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + rrf_score
                if chunk.id not in chunk_map:
                    chunk_map[chunk.id] = chunk
        
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        results = []
        for doc_id in sorted_ids[:top_k]:
            chunk = chunk_map[doc_id]
            chunk.score = rrf_scores[doc_id]
            results.append(chunk)
        
        return results, variants
    
    async def _hyde_retrieve(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievedChunk]:
        """HyDE检索"""
        if not self.hyde_generator:
            return await self._dense_retrieve(query, top_k)
        
        # 生成假设文档
        hypothetical_doc = await self.hyde_generator.generate_hypothetical_document(query)
        
        # 用假设文档检索
        hyde_embedding = await self.embedding.embed(hypothetical_doc)
        results = await self.vector_store.search(hyde_embedding, top_k=top_k)
        
        chunks = []
        for r in results:
            chunks.append(RetrievedChunk(
                id=r.id,
                content=r.metadata.get("content", ""),
                score=r.score,
                source="hyde",
                metadata=r.metadata
            ))
        
        return chunks
    
    async def retrieve(
        self,
        query: str,
        strategy: Optional[RetrievalStrategy] = None
    ) -> RAGContext:
        """检索"""
        strategy = strategy or self.config.retrieval_strategy
        top_k = self.config.top_k
        query_variants = []
        
        if strategy == RetrievalStrategy.DENSE:
            chunks = await self._dense_retrieve(query, top_k)
        elif strategy == RetrievalStrategy.SPARSE:
            chunks = await self._sparse_retrieve(query, top_k)
        elif strategy == RetrievalStrategy.HYBRID:
            chunks = await self._hybrid_retrieve(query, top_k)
        elif strategy == RetrievalStrategy.MULTI_QUERY:
            chunks, query_variants = await self._multi_query_retrieve(query, top_k)
        elif strategy == RetrievalStrategy.HYDE:
            chunks = await self._hyde_retrieve(query, top_k)
        else:
            chunks = await self._hybrid_retrieve(query, top_k)
        
        # 过滤低分
        chunks = [c for c in chunks if c.score >= self.config.min_score]
        
        # 重排序
        if chunks:
            chunks = await self.reranker.rerank(query, chunks, self.config.rerank_top_k)
        
        return RAGContext(
            chunks=chunks,
            retrieval_strategy=strategy.value,
            query_variants=query_variants
        )
    
    async def generate_answer(
        self,
        query: str,
        context: RAGContext,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AdvancedRAGResponse:
        """生成答案"""
        if not context.chunks:
            return AdvancedRAGResponse(
                answer="抱歉，未能找到相关资料来回答您的问题。",
                context=context,
                confidence=0.0
            )
        
        # 构建上下文
        context_parts = []
        for i, chunk in enumerate(context.chunks):
            source_info = chunk.metadata.get('title', chunk.id)
            context_parts.append(f"[来源{i+1}: {source_info}]\n{chunk.content}")
        
        context_text = "\n\n".join(context_parts)
        
        # 生成提示
        if self.config.citation_enabled:
            system_prompt = """你是一个专业的地方志资料助手。请基于提供的参考资料回答用户问题。
要求：
1. 回答要准确、专业
2. 引用资料时标注来源编号，如[来源1]
3. 如果资料中没有相关信息，请明确告知
4. 对于不确定的内容，要说明不确定性"""
        else:
            system_prompt = """你是一个专业的地方志资料助手。请基于提供的参考资料回答用户问题。
如果资料中没有相关信息，请明确告知。"""
        
        prompt = f"""参考资料：
{context_text}

用户问题：{query}

请基于以上资料提供准确的回答："""
        
        result = await self.inference.generate(
            prompt,
            system_prompt=system_prompt,
            history=history,
            temperature=self.config.temperature
        )
        
        # 提取引用
        citations = self._extract_citations(result.content, context.chunks)
        
        # 计算置信度
        avg_score = sum(c.score for c in context.chunks) / len(context.chunks)
        confidence = min(avg_score * len(context.chunks) / self.config.rerank_top_k, 1.0)
        
        return AdvancedRAGResponse(
            answer=result.content,
            context=context,
            confidence=confidence,
            citations=citations,
            tokens_used=result.tokens_used
        )
    
    def _extract_citations(
        self,
        answer: str,
        chunks: List[RetrievedChunk]
    ) -> List[Dict[str, Any]]:
        """提取引用"""
        citations = []
        
        # 查找引用标记
        pattern = r'\[来源(\d+)\]'
        matches = re.findall(pattern, answer)
        
        seen = set()
        for match in matches:
            idx = int(match) - 1
            if 0 <= idx < len(chunks) and idx not in seen:
                chunk = chunks[idx]
                citations.append({
                    "index": idx + 1,
                    "source": chunk.metadata.get('title', chunk.id),
                    "content_preview": chunk.content[:200],
                    "score": chunk.score
                })
                seen.add(idx)
        
        return citations
    
    async def query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        strategy: Optional[RetrievalStrategy] = None
    ) -> AdvancedRAGResponse:
        """完整RAG查询"""
        if not self._initialized:
            await self.initialize()
        
        # 检索
        context = await self.retrieve(question, strategy)
        
        # 生成答案
        response = await self.generate_answer(question, context, history)
        
        return response
    
    async def stream_query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        strategy: Optional[RetrievalStrategy] = None
    ):
        """流式RAG查询"""
        if not self._initialized:
            await self.initialize()
        
        # 检索
        context = await self.retrieve(question, strategy)
        
        if not context.chunks:
            yield "抱歉，未能找到相关资料来回答您的问题。"
            return
        
        # 构建上下文
        context_parts = []
        for i, chunk in enumerate(context.chunks):
            source_info = chunk.metadata.get('title', chunk.id)
            context_parts.append(f"[来源{i+1}: {source_info}]\n{chunk.content}")
        
        context_text = "\n\n".join(context_parts)
        
        prompt = f"""参考资料：
{context_text}

用户问题：{question}

请基于以上资料提供准确的回答："""
        
        system_prompt = "你是一个专业的地方志资料助手。请基于提供的参考资料回答用户问题。"
        
        async for chunk in self.inference.stream_generate(
            prompt,
            system_prompt=system_prompt,
            history=history
        ):
            yield chunk
