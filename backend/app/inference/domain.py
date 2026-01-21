# 地方志数据智能管理系统 - 领域增强
"""地方志专业术语、实体识别、知识图谱、历史关联"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog

logger = structlog.get_logger()


class EntityType(str, Enum):
    """实体类型"""
    PERSON = "person"           # 人物
    PLACE = "place"             # 地点
    ORGANIZATION = "organization"  # 机构
    EVENT = "event"             # 事件
    TIME = "time"               # 时间
    ARTIFACT = "artifact"       # 文物/建筑
    BOOK = "book"               # 典籍
    CONCEPT = "concept"         # 概念术语
    DYNASTY = "dynasty"         # 朝代


class RelationType(str, Enum):
    """关系类型"""
    BORN_IN = "born_in"           # 出生于
    DIED_IN = "died_in"           # 卒于
    LOCATED_IN = "located_in"     # 位于
    PART_OF = "part_of"           # 属于
    HAPPENED_IN = "happened_in"   # 发生于
    RELATED_TO = "related_to"     # 关联
    AUTHORED = "authored"         # 著作
    BUILT = "built"               # 建造
    GOVERNED = "governed"         # 管辖
    SUCCEEDED_BY = "succeeded_by"  # 继任
    CONTEMPORARY = "contemporary"  # 同时代


@dataclass
class Entity:
    """实体"""
    id: str
    name: str
    entity_type: EntityType
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_ids: List[str] = field(default_factory=list)
    confidence: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type.value,
            "aliases": self.aliases,
            "description": self.description,
            "attributes": self.attributes,
            "confidence": self.confidence
        }


@dataclass
class Relation:
    """关系"""
    source_id: str
    target_id: str
    relation_type: RelationType
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.relation_type.value,
            "attributes": self.attributes,
            "confidence": self.confidence
        }


@dataclass
class ExtractionResult:
    """提取结果"""
    entities: List[Entity]
    relations: List[Relation]
    terms: List[Dict[str, str]]
    timeline: List[Dict[str, Any]]


class DomainTerms:
    """地方志专业术语库"""
    
    # 行政区划术语
    ADMIN_TERMS = {
        "州": "古代行政区划单位，相当于现在的省级",
        "府": "明清时期的行政区划单位，在州之下",
        "县": "最基层的行政区划单位",
        "乡": "县以下的行政区划",
        "里": "古代基层行政单位",
        "都": "古代行政区划单位",
        "保": "清代基层行政单位",
        "甲": "清代基层行政单位，保下设甲",
        "图": "明清时期地方行政单位",
        "厢": "城市内的区划单位"
    }
    
    # 职官术语
    OFFICIAL_TERMS = {
        "知府": "府的最高行政长官",
        "知县": "县的最高行政长官",
        "县丞": "县令的副职",
        "主簿": "掌管文书的官员",
        "典史": "掌管刑狱的官员",
        "教谕": "掌管县学的官员",
        "训导": "教谕的副职",
        "巡检": "掌管治安的官员",
        "驿丞": "管理驿站的官员",
        "税课司大使": "掌管税务的官员"
    }
    
    # 科举术语
    EXAM_TERMS = {
        "进士": "科举最高功名",
        "举人": "乡试中式者",
        "秀才": "院试中式者",
        "贡生": "由地方选送入国子监的生员",
        "监生": "在国子监读书的学生",
        "廪生": "享受官府廪膳的生员",
        "增生": "增加的生员名额",
        "附生": "附学的生员"
    }
    
    # 建筑术语
    BUILDING_TERMS = {
        "城隍庙": "供奉城隍神的庙宇",
        "文庙": "祭祀孔子的庙宇",
        "武庙": "祭祀关公的庙宇",
        "书院": "古代教育机构",
        "义学": "免费教育的学校",
        "社学": "乡村教育机构",
        "贡院": "科举考试场所",
        "衙门": "官府办公场所",
        "牌坊": "纪念性建筑"
    }
    
    # 地方志类型
    CHRONICLE_TYPES = {
        "总志": "记载全省或全国情况的地方志",
        "府志": "记载一府情况的地方志",
        "县志": "记载一县情况的地方志",
        "乡土志": "记载乡土情况的地方志",
        "山志": "记载名山情况的专志",
        "水利志": "记载水利情况的专志"
    }
    
    @classmethod
    def get_all_terms(cls) -> Dict[str, str]:
        """获取所有术语"""
        all_terms = {}
        all_terms.update(cls.ADMIN_TERMS)
        all_terms.update(cls.OFFICIAL_TERMS)
        all_terms.update(cls.EXAM_TERMS)
        all_terms.update(cls.BUILDING_TERMS)
        all_terms.update(cls.CHRONICLE_TYPES)
        return all_terms
    
    @classmethod
    def explain_term(cls, term: str) -> Optional[str]:
        """解释术语"""
        all_terms = cls.get_all_terms()
        return all_terms.get(term)
    
    @classmethod
    def find_terms_in_text(cls, text: str) -> List[Dict[str, str]]:
        """在文本中查找术语"""
        found = []
        all_terms = cls.get_all_terms()
        
        for term, explanation in all_terms.items():
            if term in text:
                found.append({
                    "term": term,
                    "explanation": explanation,
                    "positions": [m.start() for m in re.finditer(re.escape(term), text)]
                })
        
        return found


class ChineseEraConverter:
    """中国历史纪年转换"""
    
    # 朝代年表（简化版）
    DYNASTIES = {
        "夏": (-2070, -1600),
        "商": (-1600, -1046),
        "周": (-1046, -256),
        "秦": (-221, -207),
        "汉": (-206, 220),
        "西汉": (-206, 8),
        "东汉": (25, 220),
        "三国": (220, 280),
        "晋": (265, 420),
        "南北朝": (420, 589),
        "隋": (581, 618),
        "唐": (618, 907),
        "五代": (907, 960),
        "宋": (960, 1279),
        "北宋": (960, 1127),
        "南宋": (1127, 1279),
        "元": (1271, 1368),
        "明": (1368, 1644),
        "清": (1644, 1912),
        "民国": (1912, 1949)
    }
    
    # 常用年号（部分）
    ERA_NAMES = {
        # 明朝
        "洪武": (1368, 1398),
        "永乐": (1403, 1424),
        "宣德": (1426, 1435),
        "正统": (1436, 1449),
        "景泰": (1450, 1456),
        "成化": (1465, 1487),
        "弘治": (1488, 1505),
        "正德": (1506, 1521),
        "嘉靖": (1522, 1566),
        "隆庆": (1567, 1572),
        "万历": (1573, 1620),
        "崇祯": (1628, 1644),
        # 清朝
        "顺治": (1644, 1661),
        "康熙": (1662, 1722),
        "雍正": (1723, 1735),
        "乾隆": (1736, 1795),
        "嘉庆": (1796, 1820),
        "道光": (1821, 1850),
        "咸丰": (1851, 1861),
        "同治": (1862, 1874),
        "光绪": (1875, 1908),
        "宣统": (1909, 1912)
    }
    
    @classmethod
    def era_to_year(cls, era_name: str, year_in_era: int) -> Optional[int]:
        """年号转公元年"""
        if era_name in cls.ERA_NAMES:
            start_year, end_year = cls.ERA_NAMES[era_name]
            result = start_year + year_in_era - 1
            if result <= end_year:
                return result
        return None
    
    @classmethod
    def parse_era_date(cls, text: str) -> List[Dict[str, Any]]:
        """解析文本中的年号日期"""
        results = []
        
        # 匹配年号+年的模式
        pattern = r'([a-zA-Z\u4e00-\u9fff]{2})(\d+)年'
        for match in re.finditer(pattern, text):
            era_name = match.group(1)
            year_in_era = int(match.group(2))
            
            if era_name in cls.ERA_NAMES:
                western_year = cls.era_to_year(era_name, year_in_era)
                results.append({
                    "original": match.group(0),
                    "era_name": era_name,
                    "year_in_era": year_in_era,
                    "western_year": western_year,
                    "position": match.start()
                })
        
        return results
    
    @classmethod
    def get_dynasty(cls, year: int) -> Optional[str]:
        """根据公元年获取朝代"""
        for dynasty, (start, end) in cls.DYNASTIES.items():
            if start <= year <= end:
                return dynasty
        return None


class EntityExtractor:
    """实体提取器"""
    
    def __init__(self):
        # 人物称谓后缀
        self.person_suffixes = ['公', '侯', '伯', '子', '男', '氏', '先生', '夫人', '太守', '知县', '县令']
        
        # 地点后缀
        self.place_suffixes = ['省', '府', '州', '县', '乡', '镇', '村', '里', '山', '河', '湖', '海', '寺', '庙', '塔', '桥']
        
        # 时间模式
        self.time_patterns = [
            r'[一二三四五六七八九十百千]+年',
            r'\d+年',
            r'[春夏秋冬]',
            r'[正二三四五六七八九十冬腊]月',
            r'[东西南北]汉|[东西]晋|[南北]宋|[东西]魏'
        ]
    
    def extract_entities(self, text: str) -> List[Entity]:
        """从文本中提取实体"""
        entities = []
        entity_id = 0
        
        # 提取人物
        for entity in self._extract_persons(text):
            entity.id = f"person_{entity_id}"
            entities.append(entity)
            entity_id += 1
        
        # 提取地点
        for entity in self._extract_places(text):
            entity.id = f"place_{entity_id}"
            entities.append(entity)
            entity_id += 1
        
        # 提取时间
        for entity in self._extract_times(text):
            entity.id = f"time_{entity_id}"
            entities.append(entity)
            entity_id += 1
        
        # 提取典籍
        for entity in self._extract_books(text):
            entity.id = f"book_{entity_id}"
            entities.append(entity)
            entity_id += 1
        
        return entities
    
    def _extract_persons(self, text: str) -> List[Entity]:
        """提取人物"""
        entities = []
        seen = set()
        
        # 姓名模式（姓+名，2-4字）
        name_pattern = r'(?:张|王|李|赵|刘|陈|杨|黄|周|吴|徐|孙|马|朱|胡|林|郭|何|高|罗|郑|梁|谢|宋|唐|许|邓|冯|韩|曹|彭|曾|萧|田|董|潘|袁|蔡|蒋|余|于|杜|叶|程|魏|苏|吕|丁|任|卢|姚|沈|钟|姜|崔|谭|陆|范|汪|廖|石|金|韦|贾|夏|付|方|邹|熊|白|孟|秦|邱|侯|江|尹|薛|闫|段|雷|龙|史|陶|贺|顾|毛|郝|龚|邵|万|覃|武|戴|孔|向|汤|温|康|施|文|牛|樊|葛|邢|安|齐|伍|庄|申|欧阳|司马|诸葛|上官|公孙)[\u4e00-\u9fff]{1,3}'
        
        for match in re.finditer(name_pattern, text):
            name = match.group(0)
            if len(name) >= 2 and name not in seen:
                seen.add(name)
                
                # 检查上下文是否有人物指示词
                context_start = max(0, match.start() - 10)
                context_end = min(len(text), match.end() + 10)
                context = text[context_start:context_end]
                
                confidence = 0.6
                if any(suffix in context for suffix in self.person_suffixes):
                    confidence = 0.9
                
                entities.append(Entity(
                    id="",
                    name=name,
                    entity_type=EntityType.PERSON,
                    confidence=confidence
                ))
        
        return entities
    
    def _extract_places(self, text: str) -> List[Entity]:
        """提取地点"""
        entities = []
        seen = set()
        
        for suffix in self.place_suffixes:
            pattern = rf'[\u4e00-\u9fff]{{1,6}}{suffix}'
            for match in re.finditer(pattern, text):
                place = match.group(0)
                if place not in seen:
                    seen.add(place)
                    entities.append(Entity(
                        id="",
                        name=place,
                        entity_type=EntityType.PLACE,
                        confidence=0.8
                    ))
        
        return entities
    
    def _extract_times(self, text: str) -> List[Entity]:
        """提取时间"""
        entities = []
        seen = set()
        
        # 年号日期
        era_dates = ChineseEraConverter.parse_era_date(text)
        for date_info in era_dates:
            if date_info['original'] not in seen:
                seen.add(date_info['original'])
                entities.append(Entity(
                    id="",
                    name=date_info['original'],
                    entity_type=EntityType.TIME,
                    attributes={
                        "western_year": date_info.get('western_year'),
                        "era_name": date_info.get('era_name')
                    },
                    confidence=0.95
                ))
        
        # 朝代
        for dynasty in ChineseEraConverter.DYNASTIES.keys():
            if dynasty in text and dynasty not in seen:
                seen.add(dynasty)
                entities.append(Entity(
                    id="",
                    name=dynasty,
                    entity_type=EntityType.DYNASTY,
                    confidence=0.9
                ))
        
        return entities
    
    def _extract_books(self, text: str) -> List[Entity]:
        """提取典籍"""
        entities = []
        
        # 书名号内容
        book_pattern = r'《([^》]+)》'
        for match in re.finditer(book_pattern, text):
            book_name = match.group(1)
            entities.append(Entity(
                id="",
                name=book_name,
                entity_type=EntityType.BOOK,
                confidence=0.95
            ))
        
        return entities


class RelationExtractor:
    """关系提取器"""
    
    def __init__(self):
        # 关系指示词
        self.relation_patterns = {
            RelationType.BORN_IN: ['生于', '出生于', '诞于', '籍'],
            RelationType.DIED_IN: ['卒于', '殁于', '逝于', '薨于'],
            RelationType.LOCATED_IN: ['位于', '在', '属于', '隶属'],
            RelationType.AUTHORED: ['著', '撰', '编', '纂'],
            RelationType.BUILT: ['建', '造', '修', '筑'],
            RelationType.GOVERNED: ['治', '辖', '管', '领']
        }
    
    def extract_relations(
        self,
        text: str,
        entities: List[Entity]
    ) -> List[Relation]:
        """提取关系"""
        relations = []
        
        # 简单的基于窗口的关系提取
        entity_positions = []
        for entity in entities:
            for match in re.finditer(re.escape(entity.name), text):
                entity_positions.append({
                    'entity': entity,
                    'start': match.start(),
                    'end': match.end()
                })
        
        # 按位置排序
        entity_positions.sort(key=lambda x: x['start'])
        
        # 相邻实体之间的关系
        for i in range(len(entity_positions) - 1):
            e1 = entity_positions[i]
            e2 = entity_positions[i + 1]
            
            # 检查两个实体之间的文本
            between_text = text[e1['end']:e2['start']]
            
            # 查找关系
            for rel_type, patterns in self.relation_patterns.items():
                if any(p in between_text for p in patterns):
                    relations.append(Relation(
                        source_id=e1['entity'].id,
                        target_id=e2['entity'].id,
                        relation_type=rel_type,
                        confidence=0.7
                    ))
                    break
        
        return relations


class KnowledgeGraph:
    """知识图谱"""
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self._adjacency: Dict[str, List[str]] = {}  # 邻接表
    
    def add_entity(self, entity: Entity):
        """添加实体"""
        self.entities[entity.id] = entity
        if entity.id not in self._adjacency:
            self._adjacency[entity.id] = []
    
    def add_relation(self, relation: Relation):
        """添加关系"""
        self.relations.append(relation)
        
        # 更新邻接表
        if relation.source_id not in self._adjacency:
            self._adjacency[relation.source_id] = []
        self._adjacency[relation.source_id].append(relation.target_id)
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def get_neighbors(self, entity_id: str) -> List[Entity]:
        """获取邻居实体"""
        neighbor_ids = self._adjacency.get(entity_id, [])
        return [self.entities[nid] for nid in neighbor_ids if nid in self.entities]
    
    def get_relations_for(self, entity_id: str) -> List[Relation]:
        """获取实体的所有关系"""
        return [r for r in self.relations if r.source_id == entity_id or r.target_id == entity_id]
    
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3
    ) -> Optional[List[str]]:
        """查找两个实体之间的路径"""
        if source_id not in self.entities or target_id not in self.entities:
            return None
        
        # BFS查找路径
        from collections import deque
        
        queue = deque([(source_id, [source_id])])
        visited = {source_id}
        
        while queue:
            current, path = queue.popleft()
            
            if current == target_id:
                return path
            
            if len(path) >= max_depth:
                continue
            
            for neighbor in self._adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None
    
    def get_subgraph(
        self,
        entity_id: str,
        depth: int = 2
    ) -> Tuple[List[Entity], List[Relation]]:
        """获取以实体为中心的子图"""
        entities = set()
        relations = []
        
        # BFS获取指定深度内的实体
        from collections import deque
        
        queue = deque([(entity_id, 0)])
        visited = {entity_id}
        
        while queue:
            current, d = queue.popleft()
            
            if current in self.entities:
                entities.add(current)
            
            if d < depth:
                for neighbor in self._adjacency.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, d + 1))
        
        # 获取相关关系
        for relation in self.relations:
            if relation.source_id in entities and relation.target_id in entities:
                relations.append(relation)
        
        return [self.entities[eid] for eid in entities if eid in self.entities], relations
    
    def to_dict(self) -> Dict:
        return {
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [r.to_dict() for r in self.relations],
            "stats": {
                "entity_count": len(self.entities),
                "relation_count": len(self.relations)
            }
        }


class DomainEnhancer:
    """领域增强器"""
    
    def __init__(self):
        self.entity_extractor = EntityExtractor()
        self.relation_extractor = RelationExtractor()
        self.knowledge_graph = KnowledgeGraph()
    
    def enhance_text(self, text: str) -> ExtractionResult:
        """增强文本理解"""
        # 提取实体
        entities = self.entity_extractor.extract_entities(text)
        
        # 提取关系
        relations = self.relation_extractor.extract_relations(text, entities)
        
        # 查找术语
        terms = DomainTerms.find_terms_in_text(text)
        
        # 提取时间线
        timeline = ChineseEraConverter.parse_era_date(text)
        
        # 添加到知识图谱
        for entity in entities:
            self.knowledge_graph.add_entity(entity)
        for relation in relations:
            self.knowledge_graph.add_relation(relation)
        
        return ExtractionResult(
            entities=entities,
            relations=relations,
            terms=terms,
            timeline=timeline
        )
    
    def explain_context(self, text: str) -> str:
        """生成上下文解释"""
        result = self.enhance_text(text)
        
        explanations = []
        
        # 解释术语
        if result.terms:
            explanations.append("【术语解释】")
            for term_info in result.terms[:5]:
                explanations.append(f"  · {term_info['term']}: {term_info['explanation']}")
        
        # 时间转换
        if result.timeline:
            explanations.append("\n【纪年转换】")
            for time_info in result.timeline[:5]:
                if time_info.get('western_year'):
                    explanations.append(f"  · {time_info['original']} = 公元{time_info['western_year']}年")
        
        # 实体统计
        if result.entities:
            entity_types = {}
            for e in result.entities:
                t = e.entity_type.value
                entity_types[t] = entity_types.get(t, 0) + 1
            
            explanations.append("\n【识别实体】")
            for etype, count in entity_types.items():
                explanations.append(f"  · {etype}: {count}个")
        
        return "\n".join(explanations) if explanations else "未发现需要解释的内容"
    
    def get_related_context(
        self,
        entity_name: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """获取实体的关联上下文"""
        # 查找实体
        target_entity = None
        for entity in self.knowledge_graph.entities.values():
            if entity.name == entity_name:
                target_entity = entity
                break
        
        if not target_entity:
            return {"found": False}
        
        # 获取子图
        entities, relations = self.knowledge_graph.get_subgraph(target_entity.id, depth)
        
        return {
            "found": True,
            "entity": target_entity.to_dict(),
            "related_entities": [e.to_dict() for e in entities if e.id != target_entity.id],
            "relations": [r.to_dict() for r in relations]
        }
