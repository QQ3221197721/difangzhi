# 地方志数据智能管理系统 - 推理引擎测试
"""inference模块测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

pytestmark = pytest.mark.asyncio


class TestInferenceEngine:
    """推理引擎测试"""
    
    async def test_openai_engine_init(self):
        """测试OpenAI引擎初始化"""
        from app.inference.engine import OpenAIEngine, InferenceConfig, InferenceBackend
        
        config = InferenceConfig(
            backend=InferenceBackend.OPENAI,
            model_name="gpt-3.5-turbo"
        )
        
        with patch('app.inference.engine.AsyncOpenAI') as MockClient:
            engine = OpenAIEngine(config, api_key="test-key")
            result = await engine.initialize()
            
            assert result == True
            assert engine._initialized == True
    
    async def test_generate(self):
        """测试文本生成"""
        from app.inference.engine import InferenceEngine, InferenceConfig, InferenceBackend
        
        config = InferenceConfig(
            backend=InferenceBackend.OPENAI,
            model_name="gpt-3.5-turbo"
        )
        
        with patch('app.inference.engine.AsyncOpenAI') as MockClient:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="测试回答"), finish_reason="stop")]
            mock_response.usage = MagicMock(total_tokens=100)
            
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_client
            
            engine = InferenceEngine(config, api_key="test-key")
            result = await engine.generate("测试问题")
            
            assert result.content == "测试回答"
            assert result.tokens_used == 100


class TestEmbeddingService:
    """嵌入服务测试"""
    
    async def test_local_embedding_init(self):
        """测试本地嵌入初始化"""
        from app.inference.embedding import LocalEmbedding, EmbeddingConfig, EmbeddingBackend
        
        config = EmbeddingConfig(
            backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        
        with patch('app.inference.embedding.SentenceTransformer') as MockModel:
            embedding = LocalEmbedding(config)
            result = await embedding.initialize()
            
            assert result == True
    
    async def test_embed_single(self):
        """测试单文本嵌入"""
        from app.inference.embedding import EmbeddingService, EmbeddingConfig, EmbeddingBackend
        
        config = EmbeddingConfig(
            backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,
            dimension=384
        )
        
        with patch('app.inference.embedding.SentenceTransformer') as MockModel:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.rand(384)
            MockModel.return_value = mock_model
            
            service = EmbeddingService(config)
            result = await service.embed("测试文本")
            
            assert len(result) == 384
    
    async def test_embed_batch(self):
        """测试批量嵌入"""
        from app.inference.embedding import EmbeddingService, EmbeddingConfig, EmbeddingBackend
        
        config = EmbeddingConfig(
            backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,
            dimension=384,
            batch_size=32
        )
        
        with patch('app.inference.embedding.SentenceTransformer') as MockModel:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.rand(3, 384)
            MockModel.return_value = mock_model
            
            service = EmbeddingService(config)
            result = await service.embed_batch(["文本1", "文本2", "文本3"])
            
            assert len(result) == 3
            assert len(result[0]) == 384


class TestModelManager:
    """模型管理测试"""
    
    def test_list_models(self):
        """测试列出模型"""
        from app.inference.model_manager import ModelManager, ModelType
        
        manager = ModelManager(models_dir="test_models")
        models = manager.list_models()
        
        assert len(models) > 0
    
    def test_get_model_info(self):
        """测试获取模型信息"""
        from app.inference.model_manager import ModelManager
        
        manager = ModelManager(models_dir="test_models")
        info = manager.get_model_info("paraphrase-multilingual-MiniLM-L12-v2")
        
        assert info is not None
        assert info.name == "paraphrase-multilingual-MiniLM-L12-v2"
    
    def test_register_model(self):
        """测试注册模型"""
        from app.inference.model_manager import ModelManager, ModelInfo, ModelType
        
        manager = ModelManager(models_dir="test_models")
        
        info = ModelInfo(
            name="test-model",
            model_type=ModelType.EMBEDDING,
            version="1.0.0",
            description="测试模型"
        )
        
        result = manager.register_model(info)
        assert result == True
        
        retrieved = manager.get_model_info("test-model")
        assert retrieved is not None


class TestVectorStore:
    """向量存储测试"""
    
    async def test_faiss_init(self):
        """测试FAISS初始化"""
        from app.inference.vector_store import FAISSVectorStore
        
        with patch('app.inference.vector_store.faiss') as MockFaiss:
            MockFaiss.IndexFlatIP.return_value = MagicMock()
            
            store = FAISSVectorStore(dimension=384, index_path="test_vectors")
            result = await store.initialize()
            
            assert result == True
    
    async def test_add_vectors(self):
        """测试添加向量"""
        from app.inference.vector_store import FAISSVectorStore
        
        with patch('app.inference.vector_store.faiss') as MockFaiss:
            mock_index = MagicMock()
            mock_index.ntotal = 0
            MockFaiss.IndexFlatIP.return_value = mock_index
            
            store = FAISSVectorStore(dimension=384, index_path="test_vectors")
            await store.initialize()
            
            ids = ["doc1", "doc2"]
            vectors = [np.random.rand(384).tolist() for _ in range(2)]
            metadata = [{"title": "文档1"}, {"title": "文档2"}]
            
            result = await store.add(ids, vectors, metadata)
            assert result == True
    
    async def test_search(self):
        """测试向量搜索"""
        from app.inference.vector_store import FAISSVectorStore
        
        with patch('app.inference.vector_store.faiss') as MockFaiss:
            mock_index = MagicMock()
            mock_index.ntotal = 2
            mock_index.search.return_value = (
                np.array([[0.9, 0.8]]),
                np.array([[0, 1]])
            )
            MockFaiss.IndexFlatIP.return_value = mock_index
            
            store = FAISSVectorStore(dimension=384, index_path="test_vectors")
            await store.initialize()
            store.id_map = {0: "doc1", 1: "doc2"}
            store.metadata_store = {
                "doc1": {"title": "文档1"},
                "doc2": {"title": "文档2"}
            }
            
            query = np.random.rand(384).tolist()
            results = await store.search(query, top_k=2)
            
            assert len(results) == 2
            assert results[0].id in ["doc1", "doc2"]


class TestRAGPipeline:
    """RAG管道测试"""
    
    async def test_query(self):
        """测试RAG查询"""
        from app.inference.rag import RAGPipeline, RAGConfig
        from unittest.mock import AsyncMock
        
        config = RAGConfig(top_k=3)
        
        mock_inference = MagicMock()
        mock_inference.initialize = AsyncMock(return_value=True)
        mock_inference.generate = AsyncMock(return_value=MagicMock(content="AI回答"))
        
        mock_embedding = MagicMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 384)
        
        mock_vector = MagicMock()
        mock_vector.initialize = AsyncMock(return_value=True)
        mock_vector.search = AsyncMock(return_value=[
            MagicMock(id="doc1", score=0.9, metadata={"title": "文档1", "content": "内容1"})
        ])
        
        pipeline = RAGPipeline(
            config=config,
            inference_engine=mock_inference,
            embedding_service=mock_embedding,
            vector_store=mock_vector
        )
        
        await pipeline.initialize()
        response = await pipeline.query("测试问题")
        
        assert response.answer == "AI回答"
        assert len(response.sources) > 0


class TestIntegration:
    """集成测试"""
    
    async def test_full_pipeline(self):
        """测试完整RAG流程"""
        # 这个测试需要实际的模型和向量库
        # 在CI/CD中可以跳过
        pass
