# 地方志数据智能管理系统 - 向量存储
"""向量数据库服务，支持FAISS和Chroma"""

import os
import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import asyncio
import structlog

logger = structlog.get_logger()


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    id: str
    score: float
    metadata: Dict[str, Any]


class VectorStore(ABC):
    """向量存储基类"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化"""
        pass
    
    @abstractmethod
    async def add(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadata: Optional[List[Dict]] = None
    ) -> bool:
        """添加向量"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict] = None
    ) -> List[VectorSearchResult]:
        """搜索相似向量"""
        pass
    
    @abstractmethod
    async def delete(self, ids: List[str]) -> bool:
        """删除向量"""
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """获取向量数量"""
        pass
    
    @abstractmethod
    async def save(self) -> bool:
        """持久化"""
        pass
    
    @abstractmethod
    async def load(self) -> bool:
        """加载"""
        pass


class FAISSVectorStore(VectorStore):
    """FAISS向量存储"""
    
    def __init__(
        self,
        dimension: int,
        index_path: str = "vectors/faiss",
        index_type: str = "flat"  # flat/ivf/hnsw
    ):
        self.dimension = dimension
        self.index_path = Path(index_path)
        self.index_type = index_type
        self.index = None
        self.id_map: Dict[int, str] = {}  # FAISS内部ID -> 外部ID
        self.metadata_store: Dict[str, Dict] = {}
        self._initialized = False
    
    async def initialize(self) -> bool:
        try:
            import faiss
            
            self.index_path.mkdir(parents=True, exist_ok=True)
            
            if self.index_type == "flat":
                self.index = faiss.IndexFlatIP(self.dimension)  # 内积（余弦相似度需归一化）
            elif self.index_type == "ivf":
                quantizer = faiss.IndexFlatIP(self.dimension)
                self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            elif self.index_type == "hnsw":
                self.index = faiss.IndexHNSWFlat(self.dimension, 32)
            
            # 尝试加载现有索引
            await self.load()
            
            self._initialized = True
            logger.info("FAISS vector store initialized", dimension=self.dimension)
            return True
        except Exception as e:
            logger.error("FAISS init failed", error=str(e))
            return False
    
    async def add(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadata: Optional[List[Dict]] = None
    ) -> bool:
        if not self._initialized:
            await self.initialize()
        
        try:
            vectors_np = np.array(vectors, dtype=np.float32)
            
            # 归一化（用于余弦相似度）
            norms = np.linalg.norm(vectors_np, axis=1, keepdims=True)
            vectors_np = vectors_np / norms
            
            # 获取起始ID
            start_id = self.index.ntotal
            
            # 添加向量
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.index.add, vectors_np)
            
            # 更新映射
            for i, ext_id in enumerate(ids):
                internal_id = start_id + i
                self.id_map[internal_id] = ext_id
                if metadata and i < len(metadata):
                    self.metadata_store[ext_id] = metadata[i]
            
            logger.info("Vectors added to FAISS", count=len(ids))
            return True
        except Exception as e:
            logger.error("FAISS add failed", error=str(e))
            return False
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict] = None
    ) -> List[VectorSearchResult]:
        if not self._initialized:
            await self.initialize()
        
        try:
            query_np = np.array([query_vector], dtype=np.float32)
            
            # 归一化
            norm = np.linalg.norm(query_np)
            if norm > 0:
                query_np = query_np / norm
            
            loop = asyncio.get_event_loop()
            scores, indices = await loop.run_in_executor(
                None,
                lambda: self.index.search(query_np, top_k)
            )
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:
                    continue
                ext_id = self.id_map.get(idx, str(idx))
                metadata = self.metadata_store.get(ext_id, {})
                
                # 应用过滤
                if filter:
                    match = all(
                        metadata.get(k) == v for k, v in filter.items()
                    )
                    if not match:
                        continue
                
                results.append(VectorSearchResult(
                    id=ext_id,
                    score=float(score),
                    metadata=metadata
                ))
            
            return results
        except Exception as e:
            logger.error("FAISS search failed", error=str(e))
            return []
    
    async def delete(self, ids: List[str]) -> bool:
        # FAISS不支持直接删除，需要重建索引
        # 这里简单实现：标记删除
        for ext_id in ids:
            if ext_id in self.metadata_store:
                del self.metadata_store[ext_id]
        return True
    
    async def count(self) -> int:
        if self.index:
            return self.index.ntotal
        return 0
    
    async def save(self) -> bool:
        try:
            import faiss
            
            index_file = self.index_path / "index.faiss"
            meta_file = self.index_path / "metadata.pkl"
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: faiss.write_index(self.index, str(index_file))
            )
            
            with open(meta_file, "wb") as f:
                pickle.dump({
                    "id_map": self.id_map,
                    "metadata_store": self.metadata_store
                }, f)
            
            logger.info("FAISS index saved")
            return True
        except Exception as e:
            logger.error("FAISS save failed", error=str(e))
            return False
    
    async def load(self) -> bool:
        try:
            import faiss
            
            index_file = self.index_path / "index.faiss"
            meta_file = self.index_path / "metadata.pkl"
            
            if index_file.exists():
                loop = asyncio.get_event_loop()
                self.index = await loop.run_in_executor(
                    None,
                    lambda: faiss.read_index(str(index_file))
                )
                
                if meta_file.exists():
                    with open(meta_file, "rb") as f:
                        data = pickle.load(f)
                        self.id_map = data.get("id_map", {})
                        self.metadata_store = data.get("metadata_store", {})
                
                logger.info("FAISS index loaded", count=self.index.ntotal)
                return True
            return False
        except Exception as e:
            logger.error("FAISS load failed", error=str(e))
            return False


class ChromaVectorStore(VectorStore):
    """Chroma向量存储"""
    
    def __init__(
        self,
        collection_name: str = "documents",
        persist_path: str = "vectors/chroma"
    ):
        self.collection_name = collection_name
        self.persist_path = persist_path
        self.client = None
        self.collection = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_path,
                anonymized_telemetry=False
            ))
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            self._initialized = True
            logger.info("Chroma vector store initialized")
            return True
        except Exception as e:
            logger.error("Chroma init failed", error=str(e))
            return False
    
    async def add(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadata: Optional[List[Dict]] = None
    ) -> bool:
        if not self._initialized:
            await self.initialize()
        
        try:
            self.collection.add(
                ids=ids,
                embeddings=vectors,
                metadatas=metadata or [{}] * len(ids)
            )
            logger.info("Vectors added to Chroma", count=len(ids))
            return True
        except Exception as e:
            logger.error("Chroma add failed", error=str(e))
            return False
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict] = None
    ) -> List[VectorSearchResult]:
        if not self._initialized:
            await self.initialize()
        
        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=filter
            )
            
            search_results = []
            if results["ids"]:
                for i, id_ in enumerate(results["ids"][0]):
                    score = 1 - results["distances"][0][i] if results["distances"] else 0
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    search_results.append(VectorSearchResult(
                        id=id_,
                        score=score,
                        metadata=metadata
                    ))
            
            return search_results
        except Exception as e:
            logger.error("Chroma search failed", error=str(e))
            return []
    
    async def delete(self, ids: List[str]) -> bool:
        if not self._initialized:
            await self.initialize()
        
        try:
            self.collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error("Chroma delete failed", error=str(e))
            return False
    
    async def count(self) -> int:
        if self.collection:
            return self.collection.count()
        return 0
    
    async def save(self) -> bool:
        if self.client:
            self.client.persist()
            return True
        return False
    
    async def load(self) -> bool:
        return await self.initialize()
