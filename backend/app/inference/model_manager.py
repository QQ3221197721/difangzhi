# 地方志数据智能管理系统 - 模型权重管理
"""模型下载、加载、版本管理"""

import os
import json
import hashlib
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
import structlog

logger = structlog.get_logger()


class ModelStatus(str, Enum):
    """模型状态"""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


class ModelType(str, Enum):
    """模型类型"""
    EMBEDDING = "embedding"
    LLM = "llm"
    CLASSIFIER = "classifier"
    NER = "ner"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    model_type: ModelType
    version: str = "1.0.0"
    description: str = ""
    size_mb: float = 0.0
    download_url: Optional[str] = None
    local_path: Optional[str] = None
    checksum: Optional[str] = None
    status: ModelStatus = ModelStatus.NOT_DOWNLOADED
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ModelInfo":
        data["model_type"] = ModelType(data["model_type"])
        data["status"] = ModelStatus(data["status"])
        return cls(**data)


# 预定义模型库
PREDEFINED_MODELS = {
    "paraphrase-multilingual-MiniLM-L12-v2": ModelInfo(
        name="paraphrase-multilingual-MiniLM-L12-v2",
        model_type=ModelType.EMBEDDING,
        version="1.0.0",
        description="多语言句子嵌入模型，支持50+语言",
        size_mb=471,
        download_url="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        config={"dimension": 384, "max_length": 512}
    ),
    "text2vec-base-chinese": ModelInfo(
        name="text2vec-base-chinese",
        model_type=ModelType.EMBEDDING,
        version="1.0.0",
        description="中文文本嵌入模型",
        size_mb=400,
        download_url="shibing624/text2vec-base-chinese",
        config={"dimension": 768, "max_length": 512}
    ),
    "bge-base-zh-v1.5": ModelInfo(
        name="bge-base-zh-v1.5",
        model_type=ModelType.EMBEDDING,
        version="1.5.0",
        description="BAAI中文嵌入模型",
        size_mb=400,
        download_url="BAAI/bge-base-zh-v1.5",
        config={"dimension": 768, "max_length": 512}
    ),
}


class ModelManager:
    """模型管理器"""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.models_dir / "registry.json"
        self.models: Dict[str, ModelInfo] = {}
        self._loaded_models: Dict[str, Any] = {}
        self._load_registry()
    
    def _load_registry(self):
        """加载模型注册表"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, info in data.items():
                        self.models[name] = ModelInfo.from_dict(info)
            except Exception as e:
                logger.error("Load model registry failed", error=str(e))
        
        # 添加预定义模型
        for name, info in PREDEFINED_MODELS.items():
            if name not in self.models:
                self.models[name] = info
    
    def _save_registry(self):
        """保存模型注册表"""
        data = {name: info.to_dict() for name, info in self.models.items()}
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def list_models(self, model_type: Optional[ModelType] = None) -> List[ModelInfo]:
        """列出所有模型"""
        models = list(self.models.values())
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        return models
    
    def get_model_info(self, name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self.models.get(name)
    
    def register_model(self, info: ModelInfo) -> bool:
        """注册模型"""
        self.models[info.name] = info
        self._save_registry()
        logger.info("Model registered", name=info.name)
        return True
    
    async def download_model(
        self,
        name: str,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """下载模型"""
        info = self.models.get(name)
        if not info:
            logger.error("Model not found", name=name)
            return False
        
        if info.status == ModelStatus.DOWNLOADED:
            logger.info("Model already downloaded", name=name)
            return True
        
        info.status = ModelStatus.DOWNLOADING
        self._save_registry()
        
        try:
            # 使用sentence-transformers自动下载
            if info.model_type == ModelType.EMBEDDING:
                from sentence_transformers import SentenceTransformer
                
                loop = asyncio.get_event_loop()
                model_path = self.models_dir / name
                
                await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer(
                        info.download_url or name,
                        cache_folder=str(self.models_dir)
                    )
                )
                
                info.local_path = str(model_path)
                info.status = ModelStatus.DOWNLOADED
                self._save_registry()
                
                logger.info("Model downloaded", name=name)
                return True
            
            return False
            
        except Exception as e:
            info.status = ModelStatus.ERROR
            self._save_registry()
            logger.error("Model download failed", name=name, error=str(e))
            return False
    
    async def load_model(self, name: str) -> Optional[Any]:
        """加载模型到内存"""
        if name in self._loaded_models:
            return self._loaded_models[name]
        
        info = self.models.get(name)
        if not info:
            logger.error("Model not found", name=name)
            return None
        
        # 如果未下载，先下载
        if info.status != ModelStatus.DOWNLOADED:
            if not await self.download_model(name):
                return None
        
        info.status = ModelStatus.LOADING
        self._save_registry()
        
        try:
            if info.model_type == ModelType.EMBEDDING:
                from sentence_transformers import SentenceTransformer
                
                loop = asyncio.get_event_loop()
                model = await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer(
                        info.download_url or name,
                        cache_folder=str(self.models_dir)
                    )
                )
                
                self._loaded_models[name] = model
                info.status = ModelStatus.LOADED
                self._save_registry()
                
                logger.info("Model loaded", name=name)
                return model
            
            return None
            
        except Exception as e:
            info.status = ModelStatus.ERROR
            self._save_registry()
            logger.error("Model load failed", name=name, error=str(e))
            return None
    
    def unload_model(self, name: str) -> bool:
        """卸载模型"""
        if name in self._loaded_models:
            del self._loaded_models[name]
            
            info = self.models.get(name)
            if info:
                info.status = ModelStatus.DOWNLOADED
                self._save_registry()
            
            logger.info("Model unloaded", name=name)
            return True
        return False
    
    def delete_model(self, name: str) -> bool:
        """删除模型"""
        self.unload_model(name)
        
        info = self.models.get(name)
        if info and info.local_path:
            path = Path(info.local_path)
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        
        if name in self.models and name not in PREDEFINED_MODELS:
            del self.models[name]
        elif name in self.models:
            self.models[name].status = ModelStatus.NOT_DOWNLOADED
            self.models[name].local_path = None
        
        self._save_registry()
        logger.info("Model deleted", name=name)
        return True
    
    def get_loaded_models(self) -> List[str]:
        """获取已加载的模型"""
        return list(self._loaded_models.keys())
    
    def get_disk_usage(self) -> Dict[str, float]:
        """获取模型磁盘使用情况"""
        total_size = 0
        model_sizes = {}
        
        for name, info in self.models.items():
            if info.local_path:
                path = Path(info.local_path)
                if path.exists():
                    if path.is_dir():
                        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                    else:
                        size = path.stat().st_size
                    size_mb = size / (1024 * 1024)
                    model_sizes[name] = size_mb
                    total_size += size_mb
        
        return {"total_mb": total_size, "models": model_sizes}


# 全局实例
model_manager = ModelManager()
