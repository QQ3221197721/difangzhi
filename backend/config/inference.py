# 地方志数据智能管理系统 - 推理配置
"""推理相关配置"""

# 推理引擎配置
INFERENCE_CONFIG = {
    # 默认后端
    "default_backend": "openai",  # openai/ollama/local
    
    # OpenAI配置
    "openai": {
        "model": "gpt-3.5-turbo",
        "embedding_model": "text-embedding-ada-002",
        "max_tokens": 2000,
        "temperature": 0.7,
    },
    
    # Ollama本地配置
    "ollama": {
        "base_url": "http://localhost:11434",
        "model": "qwen:7b",
        "embedding_model": "nomic-embed-text",
    },
    
    # 本地模型配置
    "local": {
        "llm_model_path": "models/llm",
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "device": "cpu",  # cpu/cuda/mps
        "quantization": None,  # 4bit/8bit/none
    },
}

# 嵌入配置
EMBEDDING_CONFIG = {
    "default_backend": "sentence_transformers",  # sentence_transformers/openai/huggingface
    
    "sentence_transformers": {
        "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
        "dimension": 384,
        "max_length": 512,
        "batch_size": 32,
        "normalize": True,
    },
    
    "chinese_models": {
        "text2vec": {
            "model_name": "shibing624/text2vec-base-chinese",
            "dimension": 768,
        },
        "bge": {
            "model_name": "BAAI/bge-base-zh-v1.5",
            "dimension": 768,
        },
    },
}

# 向量存储配置
VECTOR_STORE_CONFIG = {
    "backend": "faiss",  # faiss/chroma/milvus
    
    "faiss": {
        "index_path": "vectors/faiss",
        "index_type": "flat",  # flat/ivf/hnsw
    },
    
    "chroma": {
        "collection_name": "documents",
        "persist_path": "vectors/chroma",
    },
}

# RAG配置
RAG_CONFIG = {
    "top_k": 5,
    "min_score": 0.5,
    "max_context_length": 4000,
    "rerank": False,
    
    "system_prompt": """你是一个专业的地方志资料助手。请基于提供的参考资料回答用户问题。
如果资料中没有相关信息，请明确告知用户。回答时请引用资料来源。""",
}

# 模型仓库配置
MODEL_REGISTRY = {
    "models_dir": "models",
    "cache_dir": "models/cache",
    "auto_download": True,
    
    "predefined_models": [
        {
            "name": "paraphrase-multilingual-MiniLM-L12-v2",
            "type": "embedding",
            "source": "sentence-transformers",
        },
        {
            "name": "text2vec-base-chinese",
            "type": "embedding",
            "source": "huggingface",
        },
    ],
}
