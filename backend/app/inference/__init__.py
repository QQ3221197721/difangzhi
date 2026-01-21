# 地方志数据智能管理系统 - AI推理引擎模块
"""增强型AI推理系统，支持多后端、智能路由、高级RAG、Agent等功能"""

# 基础推理引擎
from .engine import (
    InferenceEngine,
    InferenceConfig,
    InferenceResult,
    InferenceBackend,
)

# 嵌入服务
from .embedding import (
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingBackend,
    LocalEmbedding,
    OpenAIEmbedding,
)

# 模型管理
from .model_manager import (
    ModelManager,
    ModelInfo,
    ModelStatus,
)

# 向量存储
from .vector_store import (
    VectorStore,
    FAISSVectorStore,
    ChromaVectorStore,
    VectorSearchResult,
)

# 基础RAG管道
from .rag import (
    RAGPipeline,
    RAGConfig,
    RAGResponse,
    RetrievalResult,
)

# 智能路由器
from .router import (
    SmartRouter,
    RouterConfig,
    RoutingStrategy,
    ModelEndpoint,
    TaskType,
    CircuitBreaker,
    LoadBalancer,
)

# 会话管理
from .session import (
    SessionManager,
    SessionConfig,
    Session,
    Message,
    MessageRole,
    TokenCounter,
    ContextCompressor,
)

# 高级RAG
from .advanced_rag import (
    AdvancedRAGPipeline,
    AdvancedRAGConfig,
    AdvancedRAGResponse,
    RetrievalStrategy,
    RerankStrategy,
    RetrievedChunk,
    RAGContext,
    BM25Retriever,
    QueryExpander,
    HyDEGenerator,
    Reranker,
)

# 智能Agent
from .agent import (
    ReActAgent,
    PlanningAgent,
    ChroniclesAgent,
    AgentConfig,
    AgentResult,
    AgentState,
    Tool,
    ToolCall,
    ToolResult,
    ToolRegistry,
    ThoughtStep,
)

# 语义缓存
from .cache import (
    SemanticCache,
    CacheConfig,
    CacheStrategy,
    EvictionPolicy,
    CacheEntry,
    CacheStats,
    CachedInference,
    MultiTierCache,
)

# 质量保障
from .quality import (
    QualityAssessor,
    QualityReport,
    QualityLevel,
    QualityGuard,
    HallucinationDetector,
    HallucinationReport,
    HallucinationType,
    AnswerVerifier,
    VerificationResult,
    CitationTracker,
    Citation,
)

# 领域增强
from .domain import (
    DomainEnhancer,
    DomainTerms,
    ChineseEraConverter,
    EntityExtractor,
    RelationExtractor,
    KnowledgeGraph,
    Entity,
    EntityType,
    Relation,
    RelationType,
    ExtractionResult,
)

__all__ = [
    # ===== 基础推理引擎 =====
    "InferenceEngine",
    "InferenceConfig",
    "InferenceResult",
    "InferenceBackend",
    
    # ===== 嵌入服务 =====
    "EmbeddingService",
    "EmbeddingConfig",
    "EmbeddingBackend",
    "LocalEmbedding",
    "OpenAIEmbedding",
    
    # ===== 模型管理 =====
    "ModelManager",
    "ModelInfo",
    "ModelStatus",
    
    # ===== 向量存储 =====
    "VectorStore",
    "FAISSVectorStore",
    "ChromaVectorStore",
    "VectorSearchResult",
    
    # ===== RAG管道 =====
    "RAGPipeline",
    "RAGConfig",
    "RAGResponse",
    "RetrievalResult",
    
    # ===== 智能路由器 =====
    "SmartRouter",
    "RouterConfig",
    "RoutingStrategy",
    "ModelEndpoint",
    "TaskType",
    "CircuitBreaker",
    "LoadBalancer",
    
    # ===== 会话管理 =====
    "SessionManager",
    "SessionConfig",
    "Session",
    "Message",
    "MessageRole",
    "TokenCounter",
    "ContextCompressor",
    
    # ===== 高级RAG =====
    "AdvancedRAGPipeline",
    "AdvancedRAGConfig",
    "AdvancedRAGResponse",
    "RetrievalStrategy",
    "RerankStrategy",
    "RetrievedChunk",
    "RAGContext",
    "BM25Retriever",
    "QueryExpander",
    "HyDEGenerator",
    "Reranker",
    
    # ===== 智能Agent =====
    "ReActAgent",
    "PlanningAgent",
    "ChroniclesAgent",
    "AgentConfig",
    "AgentResult",
    "AgentState",
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolRegistry",
    "ThoughtStep",
    
    # ===== 语义缓存 =====
    "SemanticCache",
    "CacheConfig",
    "CacheStrategy",
    "EvictionPolicy",
    "CacheEntry",
    "CacheStats",
    "CachedInference",
    "MultiTierCache",
    
    # ===== 质量保障 =====
    "QualityAssessor",
    "QualityReport",
    "QualityLevel",
    "QualityGuard",
    "HallucinationDetector",
    "HallucinationReport",
    "HallucinationType",
    "AnswerVerifier",
    "VerificationResult",
    "CitationTracker",
    "Citation",
    
    # ===== 领域增强 =====
    "DomainEnhancer",
    "DomainTerms",
    "ChineseEraConverter",
    "EntityExtractor",
    "RelationExtractor",
    "KnowledgeGraph",
    "Entity",
    "EntityType",
    "Relation",
    "RelationType",
    "ExtractionResult",
]
