# 地方志数据智能管理系统 - 版本与溯源模块
"""数据版本控制和来源追踪"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger()


class VersionStatus(str, Enum):
    """版本状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ChangeType(str, Enum):
    """变更类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"
    REVERT = "revert"


@dataclass
class VersionInfo:
    """版本信息"""
    version_id: str
    entity_type: str
    entity_id: str
    version_number: int
    status: VersionStatus
    created_at: datetime
    created_by: int
    change_type: ChangeType
    change_summary: str
    data_hash: str
    parent_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "version_id": self.version_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "version_number": self.version_number,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "change_type": self.change_type.value,
            "change_summary": self.change_summary,
            "data_hash": self.data_hash,
            "parent_version": self.parent_version,
            "metadata": self.metadata
        }


@dataclass
class Provenance:
    """数据溯源"""
    entity_type: str
    entity_id: str
    source_type: str        # upload/import/api/manual/ai_generated
    source_id: str          # 源ID
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    original_format: str = ""
    transformation: str = ""  # 转换说明
    created_at: datetime = None
    created_by: int = 0
    verified: bool = False
    verification_notes: str = ""
    lineage: List[str] = field(default_factory=list)  # 血缘关系
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "source_file": self.source_file,
            "original_format": self.original_format,
            "transformation": self.transformation,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "verified": self.verified,
            "verification_notes": self.verification_notes,
            "lineage": self.lineage
        }


class VersionManager:
    """版本管理器"""
    
    def __init__(self, storage_path: str = "data/versions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.versions: Dict[str, List[VersionInfo]] = {}  # entity_key -> versions
    
    def _get_entity_key(self, entity_type: str, entity_id: str) -> str:
        return f"{entity_type}:{entity_id}"
    
    def _compute_hash(self, data: Any) -> str:
        """计算数据哈希"""
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def create_version(
        self,
        entity_type: str,
        entity_id: str,
        data: Any,
        user_id: int,
        change_type: ChangeType,
        change_summary: str,
        metadata: Dict = None
    ) -> VersionInfo:
        """创建新版本"""
        entity_key = self._get_entity_key(entity_type, entity_id)
        
        # 获取版本号
        existing = self.versions.get(entity_key, [])
        version_number = len(existing) + 1
        parent_version = existing[-1].version_id if existing else None
        
        # 创建版本
        version = VersionInfo(
            version_id=f"v_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            entity_type=entity_type,
            entity_id=entity_id,
            version_number=version_number,
            status=VersionStatus.DRAFT,
            created_at=datetime.now(),
            created_by=user_id,
            change_type=change_type,
            change_summary=change_summary,
            data_hash=self._compute_hash(data),
            parent_version=parent_version,
            metadata=metadata or {}
        )
        
        # 保存版本
        if entity_key not in self.versions:
            self.versions[entity_key] = []
        self.versions[entity_key].append(version)
        
        # 持久化数据
        self._save_version_data(version, data)
        
        logger.info(
            "创建版本",
            entity=entity_key,
            version=version_number,
            change_type=change_type.value
        )
        
        return version
    
    def _save_version_data(self, version: VersionInfo, data: Any):
        """保存版本数据"""
        version_dir = self.storage_path / version.entity_type / version.entity_id
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存数据
        data_file = version_dir / f"{version.version_id}.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        # 保存元数据
        meta_file = version_dir / f"{version.version_id}_meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(version.to_dict(), f, ensure_ascii=False, indent=2)
    
    def get_version(
        self,
        entity_type: str,
        entity_id: str,
        version_id: str = None,
        version_number: int = None
    ) -> Optional[VersionInfo]:
        """获取版本"""
        entity_key = self._get_entity_key(entity_type, entity_id)
        versions = self.versions.get(entity_key, [])
        
        if version_id:
            return next((v for v in versions if v.version_id == version_id), None)
        
        if version_number:
            return next((v for v in versions if v.version_number == version_number), None)
        
        # 返回最新版本
        return versions[-1] if versions else None
    
    def get_version_data(self, version: VersionInfo) -> Optional[Any]:
        """获取版本数据"""
        data_file = self.storage_path / version.entity_type / version.entity_id / f"{version.version_id}.json"
        
        if data_file.exists():
            with open(data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def get_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[VersionInfo]:
        """获取版本历史"""
        entity_key = self._get_entity_key(entity_type, entity_id)
        versions = self.versions.get(entity_key, [])
        return list(reversed(versions))[:limit]
    
    def compare_versions(
        self,
        entity_type: str,
        entity_id: str,
        version_id_1: str,
        version_id_2: str
    ) -> Dict[str, Any]:
        """比较两个版本"""
        v1 = self.get_version(entity_type, entity_id, version_id_1)
        v2 = self.get_version(entity_type, entity_id, version_id_2)
        
        if not v1 or not v2:
            return {"error": "版本不存在"}
        
        data1 = self.get_version_data(v1)
        data2 = self.get_version_data(v2)
        
        # 简单的diff实现
        diff = {
            "version_1": v1.to_dict(),
            "version_2": v2.to_dict(),
            "changes": []
        }
        
        if isinstance(data1, dict) and isinstance(data2, dict):
            all_keys = set(data1.keys()) | set(data2.keys())
            for key in all_keys:
                val1 = data1.get(key)
                val2 = data2.get(key)
                if val1 != val2:
                    diff["changes"].append({
                        "field": key,
                        "old_value": val1,
                        "new_value": val2
                    })
        
        return diff
    
    def revert_to_version(
        self,
        entity_type: str,
        entity_id: str,
        target_version_id: str,
        user_id: int
    ) -> Optional[VersionInfo]:
        """回滚到指定版本"""
        target = self.get_version(entity_type, entity_id, target_version_id)
        if not target:
            return None
        
        data = self.get_version_data(target)
        if not data:
            return None
        
        return self.create_version(
            entity_type=entity_type,
            entity_id=entity_id,
            data=data,
            user_id=user_id,
            change_type=ChangeType.REVERT,
            change_summary=f"回滚到版本 {target.version_number}",
            metadata={"reverted_from": target_version_id}
        )
    
    def publish_version(
        self,
        entity_type: str,
        entity_id: str,
        version_id: str
    ) -> bool:
        """发布版本"""
        version = self.get_version(entity_type, entity_id, version_id)
        if version:
            version.status = VersionStatus.PUBLISHED
            return True
        return False


class ProvenanceTracker:
    """溯源追踪器"""
    
    def __init__(self, storage_path: str = "data/provenance"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.records: Dict[str, Provenance] = {}
    
    def _get_key(self, entity_type: str, entity_id: str) -> str:
        return f"{entity_type}:{entity_id}"
    
    def record_provenance(self, provenance: Provenance) -> str:
        """记录溯源信息"""
        key = self._get_key(provenance.entity_type, provenance.entity_id)
        self.records[key] = provenance
        
        # 持久化
        file_path = self.storage_path / f"{provenance.entity_type}_{provenance.entity_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(provenance.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(
            "记录溯源",
            entity=key,
            source_type=provenance.source_type
        )
        
        return key
    
    def get_provenance(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Provenance]:
        """获取溯源信息"""
        key = self._get_key(entity_type, entity_id)
        return self.records.get(key)
    
    def add_lineage(
        self,
        entity_type: str,
        entity_id: str,
        parent_entity_type: str,
        parent_entity_id: str
    ):
        """添加血缘关系"""
        provenance = self.get_provenance(entity_type, entity_id)
        if provenance:
            parent_key = self._get_key(parent_entity_type, parent_entity_id)
            if parent_key not in provenance.lineage:
                provenance.lineage.append(parent_key)
    
    def get_lineage_graph(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 3
    ) -> Dict[str, Any]:
        """获取血缘图谱"""
        key = self._get_key(entity_type, entity_id)
        provenance = self.records.get(key)
        
        if not provenance:
            return {"entity": key, "lineage": []}
        
        result = {
            "entity": key,
            "provenance": provenance.to_dict(),
            "upstream": []  # 上游数据源
        }
        
        if depth > 0 and provenance.lineage:
            for parent_key in provenance.lineage:
                parts = parent_key.split(":")
                if len(parts) == 2:
                    parent_graph = self.get_lineage_graph(parts[0], parts[1], depth - 1)
                    result["upstream"].append(parent_graph)
        
        return result
    
    def verify_provenance(
        self,
        entity_type: str,
        entity_id: str,
        verified_by: int,
        notes: str = ""
    ) -> bool:
        """验证溯源信息"""
        provenance = self.get_provenance(entity_type, entity_id)
        if provenance:
            provenance.verified = True
            provenance.verification_notes = notes
            return True
        return False
    
    def search_by_source(
        self,
        source_type: str = None,
        source_id: str = None
    ) -> List[Provenance]:
        """按来源搜索"""
        results = []
        
        for provenance in self.records.values():
            if source_type and provenance.source_type != source_type:
                continue
            if source_id and provenance.source_id != source_id:
                continue
            results.append(provenance)
        
        return results
