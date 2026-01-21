# 地方志数据智能管理系统 - 语义缓存
"""基于语义相似度的智能缓存系统"""

import asyncio
import hashlib
import json
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import structlog

logger = structlog.get_logger()


class CacheStrategy(str, Enum):
    """缓存策略"""
    EXACT = "exact"           # 精确匹配
    SEMANTIC = "semantic"     # 语义匹配
    HYBRID = "hybrid"         # 混合匹配


class EvictionPolicy(str, Enum):
    """淘汰策略"""
    LRU = "lru"               # 最近最少使用
    LFU = "lfu"               # 最不经常使用
    TTL = "ttl"               # 过期时间
    FIFO = "fifo"             # 先进先出
    ADAPTIVE = "adaptive"     # 自适应


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    query: str
    response: str
    embedding: Optional[List[float]] = None
    created_at: datetime = None
    last_accessed: datetime = None
    access_count: int = 0
    ttl_seconds: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        now = datetime.now()
        if not self.created_at:
            self.created_at = now
        if not self.last_accessed:
            self.last_accessed = now
    
    @property
    def is_expired(self) -> bool:
        """是否过期"""
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)
    
    def touch(self):
        """访问更新"""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "query": self.query,
            "response": self.response,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CacheEntry":
        return cls(
            key=data["key"],
            query=data["query"],
            response=data["response"],
            embedding=data.get("embedding"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            ttl_seconds=data.get("ttl_seconds", 3600),
            metadata=data.get("metadata", {})
        )


@dataclass
class CacheConfig:
    """缓存配置"""
    strategy: CacheStrategy = CacheStrategy.SEMANTIC
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    max_entries: int = 1000
    max_memory_mb: int = 100
    default_ttl_seconds: int = 3600
    semantic_threshold: float = 0.85
    persist_enabled: bool = True
    persist_path: str = "data/cache"
    auto_cleanup_interval: int = 300


@dataclass
class CacheStats:
    """缓存统计"""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    semantic_hits: int = 0
    exact_hits: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries
    
    def to_dict(self) -> Dict:
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "semantic_hits": self.semantic_hits,
            "exact_hits": self.exact_hits,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4)
        }


class EmbeddingIndex:
    """嵌入索引（用于语义搜索）"""
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.embeddings: List[np.ndarray] = []
        self.keys: List[str] = []
        self._faiss_index = None
    
    def add(self, key: str, embedding: List[float]):
        """添加嵌入"""
        vec = np.array(embedding, dtype=np.float32)
        
        # 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        
        self.embeddings.append(vec)
        self.keys.append(key)
        
        # 重建FAISS索引
        self._rebuild_index()
    
    def remove(self, key: str):
        """移除嵌入"""
        if key in self.keys:
            idx = self.keys.index(key)
            self.keys.pop(idx)
            self.embeddings.pop(idx)
            self._rebuild_index()
    
    def _rebuild_index(self):
        """重建FAISS索引"""
        if not self.embeddings:
            self._faiss_index = None
            return
        
        try:
            import faiss
            
            vectors = np.stack(self.embeddings)
            self._faiss_index = faiss.IndexFlatIP(self.dimension)
            self._faiss_index.add(vectors)
        except ImportError:
            self._faiss_index = None
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.8
    ) -> List[Tuple[str, float]]:
        """搜索相似嵌入"""
        if not self.embeddings:
            return []
        
        query_vec = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm
        
        # 使用FAISS
        if self._faiss_index is not None:
            scores, indices = self._faiss_index.search(
                query_vec.reshape(1, -1),
                min(top_k, len(self.keys))
            )
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and score >= threshold:
                    results.append((self.keys[idx], float(score)))
            return results
        
        # 回退到numpy计算
        embeddings_matrix = np.stack(self.embeddings)
        scores = np.dot(embeddings_matrix, query_vec)
        
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] >= threshold:
                results.append((self.keys[idx], float(scores[idx])))
        
        return results
    
    def clear(self):
        """清空索引"""
        self.embeddings.clear()
        self.keys.clear()
        self._faiss_index = None


class SemanticCache:
    """语义缓存"""
    
    def __init__(
        self,
        config: CacheConfig = None,
        embedding_fn: Optional[Callable] = None
    ):
        self.config = config or CacheConfig()
        self.embedding_fn = embedding_fn
        
        self._cache: Dict[str, CacheEntry] = {}
        self._exact_index: Dict[str, str] = {}  # query hash -> key
        self._semantic_index = EmbeddingIndex()
        self._stats = CacheStats()
        
        self._persist_path = Path(self.config.persist_path)
        self._cleanup_task: Optional[asyncio.Task] = None
        
        if self.config.persist_enabled:
            self._persist_path.mkdir(parents=True, exist_ok=True)
            self._load_cache()
    
    def _generate_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()[:16]
    
    def _query_hash(self, query: str) -> str:
        """查询哈希"""
        normalized = query.strip().lower()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    async def get(
        self,
        query: str,
        embedding: Optional[List[float]] = None
    ) -> Optional[CacheEntry]:
        """获取缓存"""
        self._stats.total_queries += 1
        
        # 1. 精确匹配
        query_hash = self._query_hash(query)
        if query_hash in self._exact_index:
            key = self._exact_index[query_hash]
            entry = self._cache.get(key)
            
            if entry and not entry.is_expired:
                entry.touch()
                self._stats.cache_hits += 1
                self._stats.exact_hits += 1
                logger.debug("Cache exact hit", query=query[:50])
                return entry
            elif entry:
                # 过期，清理
                await self._remove_entry(key)
        
        # 2. 语义匹配
        if self.config.strategy in [CacheStrategy.SEMANTIC, CacheStrategy.HYBRID]:
            if embedding is None and self.embedding_fn:
                embedding = await self._get_embedding(query)
            
            if embedding:
                similar = self._semantic_index.search(
                    embedding,
                    top_k=1,
                    threshold=self.config.semantic_threshold
                )
                
                if similar:
                    key, score = similar[0]
                    entry = self._cache.get(key)
                    
                    if entry and not entry.is_expired:
                        entry.touch()
                        self._stats.cache_hits += 1
                        self._stats.semantic_hits += 1
                        logger.debug(
                            "Cache semantic hit",
                            query=query[:50],
                            similarity=round(score, 3)
                        )
                        return entry
        
        self._stats.cache_misses += 1
        return None
    
    async def set(
        self,
        query: str,
        response: str,
        embedding: Optional[List[float]] = None,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> CacheEntry:
        """设置缓存"""
        # 检查容量
        if len(self._cache) >= self.config.max_entries:
            await self._evict()
        
        # 生成嵌入
        if embedding is None and self.embedding_fn:
            if self.config.strategy in [CacheStrategy.SEMANTIC, CacheStrategy.HYBRID]:
                embedding = await self._get_embedding(query)
        
        # 创建条目
        key = self._generate_key(query + str(time.time()))
        entry = CacheEntry(
            key=key,
            query=query,
            response=response,
            embedding=embedding,
            ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
            metadata=metadata or {}
        )
        
        # 存储
        self._cache[key] = entry
        self._exact_index[self._query_hash(query)] = key
        
        if embedding:
            self._semantic_index.add(key, embedding)
        
        # 持久化
        if self.config.persist_enabled:
            await self._save_entry(entry)
        
        logger.debug("Cache set", key=key, query=query[:50])
        return entry
    
    async def invalidate(self, query: str) -> bool:
        """使缓存失效"""
        query_hash = self._query_hash(query)
        if query_hash in self._exact_index:
            key = self._exact_index[query_hash]
            await self._remove_entry(key)
            return True
        return False
    
    async def _remove_entry(self, key: str):
        """移除条目"""
        entry = self._cache.pop(key, None)
        if entry:
            # 移除精确索引
            query_hash = self._query_hash(entry.query)
            self._exact_index.pop(query_hash, None)
            
            # 移除语义索引
            self._semantic_index.remove(key)
            
            # 删除持久化文件
            if self.config.persist_enabled:
                entry_file = self._persist_path / f"{key}.json"
                if entry_file.exists():
                    entry_file.unlink()
    
    async def _evict(self):
        """淘汰缓存"""
        if not self._cache:
            return
        
        policy = self.config.eviction_policy
        
        if policy == EvictionPolicy.LRU:
            # 最近最少使用
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_accessed
            )
            await self._remove_entry(oldest_key)
            
        elif policy == EvictionPolicy.LFU:
            # 最不经常使用
            least_used_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
            await self._remove_entry(least_used_key)
            
        elif policy == EvictionPolicy.FIFO:
            # 先进先出
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
            await self._remove_entry(oldest_key)
            
        elif policy == EvictionPolicy.TTL:
            # 清理过期
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired
            ]
            for key in expired_keys:
                await self._remove_entry(key)
            
            # 如果还满，用LRU
            if len(self._cache) >= self.config.max_entries:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].last_accessed
                )
                await self._remove_entry(oldest_key)
        
        elif policy == EvictionPolicy.ADAPTIVE:
            # 自适应：综合考虑访问时间、频率和TTL
            def score(key: str) -> float:
                entry = self._cache[key]
                age = (datetime.now() - entry.last_accessed).total_seconds()
                freq = entry.access_count + 1
                ttl_remaining = max(0, entry.ttl_seconds - (datetime.now() - entry.created_at).total_seconds())
                return freq / (age + 1) * (ttl_remaining + 1)
            
            lowest_score_key = min(self._cache.keys(), key=score)
            await self._remove_entry(lowest_score_key)
        
        self._stats.evictions += 1
    
    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本嵌入"""
        if not self.embedding_fn:
            return None
        
        try:
            if asyncio.iscoroutinefunction(self.embedding_fn):
                return await self.embedding_fn(text)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.embedding_fn, text)
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return None
    
    async def _save_entry(self, entry: CacheEntry):
        """保存条目到文件"""
        try:
            entry_file = self._persist_path / f"{entry.key}.json"
            with open(entry_file, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False)
        except Exception as e:
            logger.error("Cache save failed", key=entry.key, error=str(e))
    
    def _load_cache(self):
        """加载缓存"""
        try:
            for entry_file in self._persist_path.glob("*.json"):
                try:
                    with open(entry_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    entry = CacheEntry.from_dict(data)
                    
                    # 跳过过期条目
                    if entry.is_expired:
                        entry_file.unlink()
                        continue
                    
                    self._cache[entry.key] = entry
                    self._exact_index[self._query_hash(entry.query)] = entry.key
                    
                    if entry.embedding:
                        self._semantic_index.add(entry.key, entry.embedding)
                        
                except Exception as e:
                    logger.warning("Failed to load cache entry", file=str(entry_file), error=str(e))
            
            logger.info("Cache loaded", entries=len(self._cache))
        except Exception as e:
            logger.error("Cache load failed", error=str(e))
    
    async def cleanup(self):
        """清理过期缓存"""
        expired_keys = [
            k for k, v in self._cache.items()
            if v.is_expired
        ]
        
        for key in expired_keys:
            await self._remove_entry(key)
        
        if expired_keys:
            logger.info("Cache cleanup", removed=len(expired_keys))
        
        return len(expired_keys)
    
    async def start_auto_cleanup(self):
        """启动自动清理"""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self.config.auto_cleanup_interval)
                await self.cleanup()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_auto_cleanup(self):
        """停止自动清理"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._exact_index.clear()
        self._semantic_index.clear()
        
        if self.config.persist_enabled:
            for entry_file in self._persist_path.glob("*.json"):
                entry_file.unlink()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats.to_dict(),
            "current_entries": len(self._cache),
            "max_entries": self.config.max_entries,
            "strategy": self.config.strategy.value,
            "eviction_policy": self.config.eviction_policy.value
        }
    
    def warm_up(self, entries: List[Dict[str, str]]):
        """预热缓存"""
        async def _warm_up():
            for item in entries:
                query = item.get("query", "")
                response = item.get("response", "")
                if query and response:
                    await self.set(query, response)
        
        asyncio.create_task(_warm_up())


class CachedInference:
    """带缓存的推理封装"""
    
    def __init__(
        self,
        inference_fn: Callable,
        embedding_fn: Optional[Callable] = None,
        cache_config: CacheConfig = None
    ):
        self.inference_fn = inference_fn
        self.cache = SemanticCache(
            config=cache_config,
            embedding_fn=embedding_fn
        )
    
    async def generate(
        self,
        query: str,
        bypass_cache: bool = False,
        **kwargs
    ) -> Tuple[str, bool]:
        """
        生成响应
        返回: (响应内容, 是否缓存命中)
        """
        # 尝试从缓存获取
        if not bypass_cache:
            cached = await self.cache.get(query)
            if cached:
                return cached.response, True
        
        # 调用推理
        if asyncio.iscoroutinefunction(self.inference_fn):
            response = await self.inference_fn(query, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.inference_fn(query, **kwargs)
            )
        
        # 处理响应
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
        
        # 存入缓存
        await self.cache.set(query, response_text)
        
        return response_text, False
    
    def get_stats(self) -> Dict:
        return self.cache.get_stats()


class MultiTierCache:
    """多级缓存"""
    
    def __init__(
        self,
        embedding_fn: Optional[Callable] = None
    ):
        # L1: 热数据缓存（内存，小容量，高精度）
        self.l1_cache = SemanticCache(
            config=CacheConfig(
                strategy=CacheStrategy.EXACT,
                max_entries=100,
                default_ttl_seconds=300,  # 5分钟
                persist_enabled=False
            ),
            embedding_fn=embedding_fn
        )
        
        # L2: 语义缓存（内存+磁盘，中容量）
        self.l2_cache = SemanticCache(
            config=CacheConfig(
                strategy=CacheStrategy.SEMANTIC,
                max_entries=1000,
                semantic_threshold=0.9,
                default_ttl_seconds=3600,  # 1小时
                persist_enabled=True,
                persist_path="data/cache/l2"
            ),
            embedding_fn=embedding_fn
        )
        
        # L3: 冷数据缓存（磁盘，大容量，低阈值）
        self.l3_cache = SemanticCache(
            config=CacheConfig(
                strategy=CacheStrategy.SEMANTIC,
                max_entries=10000,
                semantic_threshold=0.8,
                default_ttl_seconds=86400,  # 24小时
                persist_enabled=True,
                persist_path="data/cache/l3"
            ),
            embedding_fn=embedding_fn
        )
    
    async def get(
        self,
        query: str,
        embedding: Optional[List[float]] = None
    ) -> Tuple[Optional[CacheEntry], str]:
        """
        获取缓存
        返回: (缓存条目, 命中层级)
        """
        # L1
        entry = await self.l1_cache.get(query, embedding)
        if entry:
            return entry, "L1"
        
        # L2
        entry = await self.l2_cache.get(query, embedding)
        if entry:
            # 提升到L1
            await self.l1_cache.set(
                entry.query,
                entry.response,
                entry.embedding,
                ttl_seconds=300
            )
            return entry, "L2"
        
        # L3
        entry = await self.l3_cache.get(query, embedding)
        if entry:
            # 提升到L2
            await self.l2_cache.set(
                entry.query,
                entry.response,
                entry.embedding,
                ttl_seconds=3600
            )
            return entry, "L3"
        
        return None, "MISS"
    
    async def set(
        self,
        query: str,
        response: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict] = None
    ):
        """设置缓存（写入所有层）"""
        await asyncio.gather(
            self.l1_cache.set(query, response, embedding, 300, metadata),
            self.l2_cache.set(query, response, embedding, 3600, metadata),
            self.l3_cache.set(query, response, embedding, 86400, metadata)
        )
    
    def get_stats(self) -> Dict:
        return {
            "l1": self.l1_cache.get_stats(),
            "l2": self.l2_cache.get_stats(),
            "l3": self.l3_cache.get_stats()
        }
