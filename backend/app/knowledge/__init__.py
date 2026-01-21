# 地方志数据智能管理系统 - 知识沉淀模块
"""项目经验、最佳实践和知识库管理"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
import structlog

logger = structlog.get_logger()


class KnowledgeType(str, Enum):
    """知识类型"""
    BEST_PRACTICE = "best_practice"    # 最佳实践
    LESSON_LEARNED = "lesson_learned"  # 经验教训
    PATTERN = "pattern"                # 设计模式
    TROUBLESHOOTING = "troubleshooting"  # 故障排查
    FAQ = "faq"                        # 常见问题
    TUTORIAL = "tutorial"              # 教程
    REFERENCE = "reference"            # 参考文档
    DECISION = "decision"              # 决策记录


class KnowledgeStatus(str, Enum):
    """知识状态"""
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class KnowledgeEntry:
    """知识条目"""
    id: str
    title: str
    content: str
    knowledge_type: KnowledgeType
    status: KnowledgeStatus
    tags: List[str]
    created_at: datetime
    created_by: int
    updated_at: datetime = None
    updated_by: int = None
    views: int = 0
    likes: int = 0
    related_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "knowledge_type": self.knowledge_type.value,
            "status": self.status.value,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
            "views": self.views,
            "likes": self.likes,
            "related_ids": self.related_ids,
            "metadata": self.metadata
        }


@dataclass
class IncidentPostmortem:
    """事故复盘"""
    id: str
    title: str
    incident_date: datetime
    severity: str  # P0/P1/P2/P3
    duration_minutes: int
    impact: str
    root_cause: str
    timeline: List[Dict[str, Any]]
    actions_taken: List[str]
    lessons_learned: List[str]
    prevention_measures: List[str]
    status: str = "draft"
    created_by: int = 0
    created_at: datetime = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "incident_date": self.incident_date.isoformat(),
            "severity": self.severity,
            "duration_minutes": self.duration_minutes,
            "impact": self.impact,
            "root_cause": self.root_cause,
            "timeline": self.timeline,
            "actions_taken": self.actions_taken,
            "lessons_learned": self.lessons_learned,
            "prevention_measures": self.prevention_measures,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DecisionRecord:
    """决策记录"""
    id: str
    title: str
    context: str           # 背景
    decision: str          # 决策
    alternatives: List[str]  # 备选方案
    rationale: str         # 理由
    consequences: str      # 后果
    status: str = "proposed"  # proposed/accepted/deprecated/superseded
    stakeholders: List[str] = field(default_factory=list)
    created_by: int = 0
    created_at: datetime = None
    superseded_by: str = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "decision": self.decision,
            "alternatives": self.alternatives,
            "rationale": self.rationale,
            "consequences": self.consequences,
            "status": self.status,
            "stakeholders": self.stakeholders,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "superseded_by": self.superseded_by
        }


class KnowledgeBase:
    """知识库"""
    
    def __init__(self, storage_path: str = "data/knowledge"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.postmortems: Dict[str, IncidentPostmortem] = {}
        self.decisions: Dict[str, DecisionRecord] = {}
        
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> entry_ids
        
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        entries_file = self.storage_path / "entries.json"
        if entries_file.exists():
            try:
                with open(entries_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        item["knowledge_type"] = KnowledgeType(item["knowledge_type"])
                        item["status"] = KnowledgeStatus(item["status"])
                        item["created_at"] = datetime.fromisoformat(item["created_at"])
                        item["updated_at"] = datetime.fromisoformat(item["updated_at"])
                        entry = KnowledgeEntry(**item)
                        self.entries[entry.id] = entry
                        self._index_tags(entry)
            except Exception as e:
                logger.error("加载知识库失败", error=str(e))
    
    def _save_data(self):
        """保存数据"""
        entries_file = self.storage_path / "entries.json"
        with open(entries_file, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self.entries.values()], f, ensure_ascii=False, indent=2)
    
    def _index_tags(self, entry: KnowledgeEntry):
        """索引标签"""
        for tag in entry.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(entry.id)
    
    def create_entry(
        self,
        title: str,
        content: str,
        knowledge_type: KnowledgeType,
        tags: List[str],
        user_id: int,
        metadata: Dict = None
    ) -> KnowledgeEntry:
        """创建知识条目"""
        entry = KnowledgeEntry(
            id=f"kb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            title=title,
            content=content,
            knowledge_type=knowledge_type,
            status=KnowledgeStatus.DRAFT,
            tags=tags,
            created_at=datetime.now(),
            created_by=user_id,
            metadata=metadata or {}
        )
        
        self.entries[entry.id] = entry
        self._index_tags(entry)
        self._save_data()
        
        logger.info("创建知识条目", id=entry.id, title=title)
        return entry
    
    def update_entry(
        self,
        entry_id: str,
        user_id: int,
        title: str = None,
        content: str = None,
        tags: List[str] = None
    ) -> Optional[KnowledgeEntry]:
        """更新知识条目"""
        entry = self.entries.get(entry_id)
        if not entry:
            return None
        
        if title:
            entry.title = title
        if content:
            entry.content = content
        if tags:
            entry.tags = tags
            self._index_tags(entry)
        
        entry.updated_at = datetime.now()
        entry.updated_by = user_id
        
        self._save_data()
        return entry
    
    def publish_entry(self, entry_id: str) -> bool:
        """发布知识条目"""
        entry = self.entries.get(entry_id)
        if entry:
            entry.status = KnowledgeStatus.PUBLISHED
            self._save_data()
            return True
        return False
    
    def search(
        self,
        query: str = None,
        knowledge_type: KnowledgeType = None,
        tags: List[str] = None,
        status: KnowledgeStatus = None,
        limit: int = 50
    ) -> List[KnowledgeEntry]:
        """搜索知识条目"""
        results = []
        
        for entry in self.entries.values():
            # 状态过滤
            if status and entry.status != status:
                continue
            
            # 类型过滤
            if knowledge_type and entry.knowledge_type != knowledge_type:
                continue
            
            # 标签过滤
            if tags:
                if not any(tag in entry.tags for tag in tags):
                    continue
            
            # 关键词搜索
            if query:
                query_lower = query.lower()
                if (query_lower not in entry.title.lower() and 
                    query_lower not in entry.content.lower()):
                    continue
            
            results.append(entry)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_by_tag(self, tag: str) -> List[KnowledgeEntry]:
        """按标签获取"""
        entry_ids = self._tag_index.get(tag, set())
        return [self.entries[id] for id in entry_ids if id in self.entries]
    
    def increment_views(self, entry_id: str):
        """增加浏览量"""
        entry = self.entries.get(entry_id)
        if entry:
            entry.views += 1
    
    def like_entry(self, entry_id: str):
        """点赞"""
        entry = self.entries.get(entry_id)
        if entry:
            entry.likes += 1
    
    def get_popular(self, limit: int = 10) -> List[KnowledgeEntry]:
        """获取热门条目"""
        published = [e for e in self.entries.values() if e.status == KnowledgeStatus.PUBLISHED]
        return sorted(published, key=lambda x: x.views + x.likes * 2, reverse=True)[:limit]
    
    def get_recent(self, limit: int = 10) -> List[KnowledgeEntry]:
        """获取最新条目"""
        published = [e for e in self.entries.values() if e.status == KnowledgeStatus.PUBLISHED]
        return sorted(published, key=lambda x: x.updated_at, reverse=True)[:limit]
    
    # 事故复盘管理
    def create_postmortem(self, postmortem: IncidentPostmortem) -> str:
        """创建事故复盘"""
        self.postmortems[postmortem.id] = postmortem
        
        # 保存
        file_path = self.storage_path / "postmortems" / f"{postmortem.id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(postmortem.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info("创建事故复盘", id=postmortem.id, title=postmortem.title)
        return postmortem.id
    
    def get_postmortem(self, id: str) -> Optional[IncidentPostmortem]:
        """获取事故复盘"""
        return self.postmortems.get(id)
    
    def list_postmortems(
        self,
        severity: str = None,
        limit: int = 50
    ) -> List[IncidentPostmortem]:
        """列出事故复盘"""
        results = list(self.postmortems.values())
        
        if severity:
            results = [p for p in results if p.severity == severity]
        
        return sorted(results, key=lambda x: x.incident_date, reverse=True)[:limit]
    
    # 决策记录管理
    def create_decision(self, decision: DecisionRecord) -> str:
        """创建决策记录"""
        self.decisions[decision.id] = decision
        
        # 保存
        file_path = self.storage_path / "decisions" / f"{decision.id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info("创建决策记录", id=decision.id, title=decision.title)
        return decision.id
    
    def get_decision(self, id: str) -> Optional[DecisionRecord]:
        """获取决策记录"""
        return self.decisions.get(id)
    
    def list_decisions(
        self,
        status: str = None,
        limit: int = 50
    ) -> List[DecisionRecord]:
        """列出决策记录"""
        results = list(self.decisions.values())
        
        if status:
            results = [d for d in results if d.status == status]
        
        return sorted(results, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def supersede_decision(self, old_id: str, new_id: str):
        """替代决策"""
        old = self.decisions.get(old_id)
        if old:
            old.status = "superseded"
            old.superseded_by = new_id


# 知识导出
class KnowledgeExporter:
    """知识导出器"""
    
    @staticmethod
    def to_markdown(entry: KnowledgeEntry) -> str:
        """导出为Markdown"""
        md = f"# {entry.title}\n\n"
        md += f"**类型**: {entry.knowledge_type.value}\n"
        md += f"**标签**: {', '.join(entry.tags)}\n"
        md += f"**创建时间**: {entry.created_at.strftime('%Y-%m-%d')}\n\n"
        md += "---\n\n"
        md += entry.content
        return md
    
    @staticmethod
    def postmortem_to_markdown(postmortem: IncidentPostmortem) -> str:
        """事故复盘导出为Markdown"""
        md = f"# 事故复盘: {postmortem.title}\n\n"
        md += f"**日期**: {postmortem.incident_date.strftime('%Y-%m-%d')}\n"
        md += f"**严重程度**: {postmortem.severity}\n"
        md += f"**持续时间**: {postmortem.duration_minutes}分钟\n\n"
        
        md += "## 影响范围\n\n"
        md += f"{postmortem.impact}\n\n"
        
        md += "## 根本原因\n\n"
        md += f"{postmortem.root_cause}\n\n"
        
        md += "## 时间线\n\n"
        for event in postmortem.timeline:
            md += f"- **{event.get('time', '')}**: {event.get('description', '')}\n"
        
        md += "\n## 经验教训\n\n"
        for lesson in postmortem.lessons_learned:
            md += f"- {lesson}\n"
        
        md += "\n## 改进措施\n\n"
        for measure in postmortem.prevention_measures:
            md += f"- {measure}\n"
        
        return md
