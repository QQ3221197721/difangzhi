# 地方志数据智能管理系统 - 配置模块
"""配置文件入口"""

from .inference import (
    INFERENCE_CONFIG,
    EMBEDDING_CONFIG,
    VECTOR_STORE_CONFIG,
    RAG_CONFIG,
    MODEL_REGISTRY,
)

__all__ = [
    "INFERENCE_CONFIG",
    "EMBEDDING_CONFIG",
    "VECTOR_STORE_CONFIG",
    "RAG_CONFIG",
    "MODEL_REGISTRY",
]
