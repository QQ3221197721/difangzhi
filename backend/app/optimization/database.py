"""
数据库优化工具 - 索引分析、慢查询、分表策略、查询分析
Database Optimization - Index Analysis, Slow Query, Sharding Strategy
"""

import asyncio
import hashlib
import re
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import logging

from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

logger = logging.getLogger(__name__)


# ==================== 索引分析 ====================

class IndexType(str, Enum):
    """索引类型"""
    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"
    GIST = "gist"
    BRIN = "brin"
    FULLTEXT = "fulltext"


@dataclass
class IndexInfo:
    """索引信息"""
    name: str
    table: str
    columns: List[str]
    index_type: IndexType
    is_unique: bool = False
    is_primary: bool = False
    size_bytes: int = 0
    scans: int = 0
    tuples_read: int = 0
    tuples_fetched: int = 0
    
    @property
    def efficiency(self) -> float:
        """索引效率"""
        if self.tuples_read == 0:
            return 0.0
        return self.tuples_fetched / self.tuples_read


@dataclass
class IndexRecommendation:
    """索引建议"""
    table: str
    columns: List[str]
    index_type: IndexType
    reason: str
    estimated_improvement: float
    create_statement: str
    priority: int = 1  # 1-高, 2-中, 3-低


class IndexAnalyzer:
    """索引分析器"""
    
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._query_patterns: Dict[str, int] = defaultdict(int)
        self._column_access: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    async def analyze_table(self, table_name: str) -> Dict[str, Any]:
        """分析表的索引情况"""
        async with AsyncSession(self.engine) as session:
            # 获取现有索引
            indexes = await self._get_indexes(session, table_name)
            
            # 获取索引使用统计
            stats = await self._get_index_stats(session, table_name)
            
            # 生成建议
            recommendations = await self._generate_recommendations(
                session, table_name, indexes
            )
            
            # 检测冗余索引
            redundant = self._detect_redundant_indexes(indexes)
            
            return {
                "table": table_name,
                "indexes": [self._index_to_dict(idx) for idx in indexes],
                "stats": stats,
                "recommendations": [self._rec_to_dict(r) for r in recommendations],
                "redundant_indexes": redundant
            }
    
    async def _get_indexes(
        self,
        session: AsyncSession,
        table_name: str
    ) -> List[IndexInfo]:
        """获取表的索引"""
        # PostgreSQL查询
        query = text("""
            SELECT
                i.relname as index_name,
                a.attname as column_name,
                am.amname as index_type,
                ix.indisunique as is_unique,
                ix.indisprimary as is_primary,
                pg_relation_size(i.oid) as size_bytes
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_am am ON am.oid = i.relam
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE t.relname = :table_name
            ORDER BY i.relname, array_position(ix.indkey, a.attnum)
        """)
        
        try:
            result = await session.execute(query, {"table_name": table_name})
            rows = result.fetchall()
            
            # 按索引名分组
            index_map: Dict[str, IndexInfo] = {}
            for row in rows:
                name = row[0]
                if name not in index_map:
                    index_map[name] = IndexInfo(
                        name=name,
                        table=table_name,
                        columns=[],
                        index_type=IndexType(row[2]) if row[2] in [e.value for e in IndexType] else IndexType.BTREE,
                        is_unique=row[3],
                        is_primary=row[4],
                        size_bytes=row[5] or 0
                    )
                index_map[name].columns.append(row[1])
            
            return list(index_map.values())
        except Exception as e:
            logger.error(f"获取索引失败: {e}")
            return []
    
    async def _get_index_stats(
        self,
        session: AsyncSession,
        table_name: str
    ) -> Dict[str, Any]:
        """获取索引统计"""
        query = text("""
            SELECT
                indexrelname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes
            WHERE relname = :table_name
        """)
        
        try:
            result = await session.execute(query, {"table_name": table_name})
            rows = result.fetchall()
            
            return {
                row[0]: {
                    "scans": row[1],
                    "tuples_read": row[2],
                    "tuples_fetched": row[3]
                }
                for row in rows
            }
        except Exception as e:
            logger.error(f"获取索引统计失败: {e}")
            return {}
    
    async def _generate_recommendations(
        self,
        session: AsyncSession,
        table_name: str,
        existing_indexes: List[IndexInfo]
    ) -> List[IndexRecommendation]:
        """生成索引建议"""
        recommendations = []
        
        # 获取表结构
        columns = await self._get_table_columns(session, table_name)
        existing_columns = {
            tuple(idx.columns) for idx in existing_indexes
        }
        
        # 检查常用查询列
        for col, access_count in self._column_access[table_name].items():
            if access_count > 100 and (col,) not in existing_columns:
                recommendations.append(IndexRecommendation(
                    table=table_name,
                    columns=[col],
                    index_type=IndexType.BTREE,
                    reason=f"列 {col} 访问频繁 ({access_count} 次)",
                    estimated_improvement=0.3,
                    create_statement=f"CREATE INDEX idx_{table_name}_{col} ON {table_name} ({col})",
                    priority=2
                ))
        
        # 检查外键
        fk_columns = await self._get_foreign_keys(session, table_name)
        for fk_col in fk_columns:
            if (fk_col,) not in existing_columns:
                recommendations.append(IndexRecommendation(
                    table=table_name,
                    columns=[fk_col],
                    index_type=IndexType.BTREE,
                    reason=f"外键列 {fk_col} 没有索引",
                    estimated_improvement=0.5,
                    create_statement=f"CREATE INDEX idx_{table_name}_{fk_col} ON {table_name} ({fk_col})",
                    priority=1
                ))
        
        return recommendations
    
    def _detect_redundant_indexes(
        self,
        indexes: List[IndexInfo]
    ) -> List[Dict[str, str]]:
        """检测冗余索引"""
        redundant = []
        
        for i, idx1 in enumerate(indexes):
            for idx2 in indexes[i+1:]:
                # 检查是否是前缀索引
                cols1 = idx1.columns
                cols2 = idx2.columns
                
                if len(cols1) < len(cols2) and cols2[:len(cols1)] == cols1:
                    redundant.append({
                        "redundant_index": idx1.name,
                        "covered_by": idx2.name,
                        "reason": f"索引 {idx1.name} 被 {idx2.name} 覆盖"
                    })
                elif len(cols2) < len(cols1) and cols1[:len(cols2)] == cols2:
                    redundant.append({
                        "redundant_index": idx2.name,
                        "covered_by": idx1.name,
                        "reason": f"索引 {idx2.name} 被 {idx1.name} 覆盖"
                    })
        
        return redundant
    
    async def _get_table_columns(
        self,
        session: AsyncSession,
        table_name: str
    ) -> List[str]:
        """获取表列"""
        query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name
        """)
        
        result = await session.execute(query, {"table_name": table_name})
        return [row[0] for row in result.fetchall()]
    
    async def _get_foreign_keys(
        self,
        session: AsyncSession,
        table_name: str
    ) -> List[str]:
        """获取外键列"""
        query = text("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_name = :table_name 
                AND tc.constraint_type = 'FOREIGN KEY'
        """)
        
        result = await session.execute(query, {"table_name": table_name})
        return [row[0] for row in result.fetchall()]
    
    def record_query(self, query: str, table: str, columns: List[str]):
        """记录查询访问"""
        self._query_patterns[query] += 1
        for col in columns:
            self._column_access[table][col] += 1
    
    def _index_to_dict(self, idx: IndexInfo) -> Dict:
        return {
            "name": idx.name,
            "columns": idx.columns,
            "type": idx.index_type.value,
            "is_unique": idx.is_unique,
            "is_primary": idx.is_primary,
            "size_bytes": idx.size_bytes
        }
    
    def _rec_to_dict(self, rec: IndexRecommendation) -> Dict:
        return {
            "table": rec.table,
            "columns": rec.columns,
            "type": rec.index_type.value,
            "reason": rec.reason,
            "priority": rec.priority,
            "create_statement": rec.create_statement
        }


# ==================== 慢查询分析 ====================

@dataclass
class SlowQuery:
    """慢查询记录"""
    query: str
    query_hash: str
    execution_time_ms: float
    rows_examined: int
    rows_returned: int
    timestamp: datetime
    user: str = ""
    database: str = ""
    explain_plan: Optional[str] = None


class SlowQueryAnalyzer:
    """慢查询分析器"""
    
    def __init__(
        self,
        engine: AsyncEngine,
        threshold_ms: float = 1000,
        max_history: int = 10000
    ):
        self.engine = engine
        self.threshold_ms = threshold_ms
        self.max_history = max_history
        self._slow_queries: List[SlowQuery] = []
        self._query_stats: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "total_time_ms": 0,
            "max_time_ms": 0,
            "avg_time_ms": 0
        })
    
    def record(
        self,
        query: str,
        execution_time_ms: float,
        rows_examined: int = 0,
        rows_returned: int = 0
    ):
        """记录查询"""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        
        # 更新统计
        stats = self._query_stats[query_hash]
        stats["count"] += 1
        stats["total_time_ms"] += execution_time_ms
        stats["max_time_ms"] = max(stats["max_time_ms"], execution_time_ms)
        stats["avg_time_ms"] = stats["total_time_ms"] / stats["count"]
        stats["query"] = query[:500]  # 保存查询片段
        
        # 记录慢查询
        if execution_time_ms >= self.threshold_ms:
            slow_query = SlowQuery(
                query=query,
                query_hash=query_hash,
                execution_time_ms=execution_time_ms,
                rows_examined=rows_examined,
                rows_returned=rows_returned,
                timestamp=datetime.now()
            )
            
            self._slow_queries.append(slow_query)
            
            # 保持历史记录在限制内
            if len(self._slow_queries) > self.max_history:
                self._slow_queries = self._slow_queries[-self.max_history//2:]
            
            logger.warning(
                f"慢查询: {execution_time_ms:.2f}ms, "
                f"rows={rows_examined}/{rows_returned}, "
                f"query={query[:100]}..."
            )
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """分析查询"""
        async with AsyncSession(self.engine) as session:
            # 获取执行计划
            explain_query = f"EXPLAIN ANALYZE {query}"
            try:
                result = await session.execute(text(explain_query))
                explain_plan = "\n".join(row[0] for row in result.fetchall())
            except Exception as e:
                explain_plan = f"Error: {e}"
            
            # 解析执行计划
            analysis = self._parse_explain(explain_plan)
            
            return {
                "query": query,
                "explain_plan": explain_plan,
                "analysis": analysis,
                "recommendations": self._generate_query_recommendations(query, analysis)
            }
    
    def _parse_explain(self, explain_plan: str) -> Dict[str, Any]:
        """解析执行计划"""
        analysis = {
            "has_seq_scan": "Seq Scan" in explain_plan,
            "has_index_scan": "Index Scan" in explain_plan or "Index Only Scan" in explain_plan,
            "has_sort": "Sort" in explain_plan,
            "has_hash_join": "Hash Join" in explain_plan,
            "has_nested_loop": "Nested Loop" in explain_plan,
            "estimated_cost": 0,
            "actual_time": 0,
            "rows_estimated": 0,
            "rows_actual": 0
        }
        
        # 提取成本
        cost_match = re.search(r'cost=(\d+\.?\d*)\.\.(\d+\.?\d*)', explain_plan)
        if cost_match:
            analysis["estimated_cost"] = float(cost_match.group(2))
        
        # 提取实际时间
        time_match = re.search(r'actual time=(\d+\.?\d*)\.\.(\d+\.?\d*)', explain_plan)
        if time_match:
            analysis["actual_time"] = float(time_match.group(2))
        
        # 提取行数
        rows_match = re.search(r'rows=(\d+)', explain_plan)
        if rows_match:
            analysis["rows_actual"] = int(rows_match.group(1))
        
        return analysis
    
    def _generate_query_recommendations(
        self,
        query: str,
        analysis: Dict[str, Any]
    ) -> List[str]:
        """生成查询优化建议"""
        recommendations = []
        
        if analysis["has_seq_scan"] and not analysis["has_index_scan"]:
            recommendations.append("考虑为查询条件列添加索引以避免全表扫描")
        
        if analysis["has_sort"]:
            recommendations.append("考虑为ORDER BY列添加索引以避免排序")
        
        if analysis["has_nested_loop"]:
            recommendations.append("嵌套循环连接可能在大表上性能较差，考虑优化连接条件")
        
        # 检查SELECT *
        if re.search(r'SELECT\s+\*', query, re.IGNORECASE):
            recommendations.append("避免使用SELECT *，明确指定需要的列")
        
        # 检查LIKE '%xxx%'
        if re.search(r"LIKE\s+'%[^']+%'", query, re.IGNORECASE):
            recommendations.append("前缀通配符LIKE无法使用索引，考虑全文搜索")
        
        # 检查NOT IN
        if re.search(r'\bNOT\s+IN\b', query, re.IGNORECASE):
            recommendations.append("NOT IN可能性能较差，考虑使用NOT EXISTS或LEFT JOIN")
        
        return recommendations
    
    def get_top_slow_queries(
        self,
        limit: int = 20,
        order_by: str = "avg_time"
    ) -> List[Dict]:
        """获取最慢的查询"""
        stats_list = [
            {"hash": k, **v}
            for k, v in self._query_stats.items()
        ]
        
        if order_by == "avg_time":
            stats_list.sort(key=lambda x: x["avg_time_ms"], reverse=True)
        elif order_by == "total_time":
            stats_list.sort(key=lambda x: x["total_time_ms"], reverse=True)
        elif order_by == "count":
            stats_list.sort(key=lambda x: x["count"], reverse=True)
        
        return stats_list[:limit]
    
    def get_recent_slow_queries(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict]:
        """获取最近的慢查询"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent = [
            {
                "query": sq.query[:500],
                "hash": sq.query_hash,
                "time_ms": sq.execution_time_ms,
                "rows_examined": sq.rows_examined,
                "rows_returned": sq.rows_returned,
                "timestamp": sq.timestamp.isoformat()
            }
            for sq in self._slow_queries
            if sq.timestamp >= cutoff
        ]
        
        return recent[-limit:]


# ==================== 分表策略 ====================

class ShardingStrategy(str, Enum):
    """分片策略"""
    HASH = "hash"           # 哈希分片
    RANGE = "range"         # 范围分片
    LIST = "list"           # 列表分片
    DATE = "date"           # 日期分片
    COMPOSITE = "composite" # 组合分片


@dataclass
class ShardConfig:
    """分片配置"""
    table_name: str
    shard_key: str
    strategy: ShardingStrategy
    shard_count: int = 16
    date_format: str = "%Y%m"  # 用于日期分片
    ranges: List[Tuple[Any, Any]] = field(default_factory=list)  # 用于范围分片
    list_values: Dict[str, List[Any]] = field(default_factory=dict)  # 用于列表分片


class ShardRouter:
    """分片路由器"""
    
    def __init__(self):
        self._configs: Dict[str, ShardConfig] = {}
    
    def register(self, config: ShardConfig):
        """注册分片配置"""
        self._configs[config.table_name] = config
        logger.info(f"注册分片表: {config.table_name}, 策略: {config.strategy.value}")
    
    def route(self, table_name: str, shard_key_value: Any) -> str:
        """路由到具体分片"""
        if table_name not in self._configs:
            return table_name
        
        config = self._configs[table_name]
        
        if config.strategy == ShardingStrategy.HASH:
            return self._hash_route(config, shard_key_value)
        elif config.strategy == ShardingStrategy.RANGE:
            return self._range_route(config, shard_key_value)
        elif config.strategy == ShardingStrategy.LIST:
            return self._list_route(config, shard_key_value)
        elif config.strategy == ShardingStrategy.DATE:
            return self._date_route(config, shard_key_value)
        
        return table_name
    
    def _hash_route(self, config: ShardConfig, value: Any) -> str:
        """哈希路由"""
        hash_value = hash(str(value))
        shard_id = abs(hash_value) % config.shard_count
        return f"{config.table_name}_{shard_id:02d}"
    
    def _range_route(self, config: ShardConfig, value: Any) -> str:
        """范围路由"""
        for i, (start, end) in enumerate(config.ranges):
            if start <= value < end:
                return f"{config.table_name}_{i:02d}"
        
        # 默认最后一个分片
        return f"{config.table_name}_{len(config.ranges):02d}"
    
    def _list_route(self, config: ShardConfig, value: Any) -> str:
        """列表路由"""
        for shard_name, values in config.list_values.items():
            if value in values:
                return f"{config.table_name}_{shard_name}"
        
        return f"{config.table_name}_default"
    
    def _date_route(self, config: ShardConfig, value: Any) -> str:
        """日期路由"""
        if isinstance(value, datetime):
            suffix = value.strftime(config.date_format)
        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                suffix = dt.strftime(config.date_format)
            except ValueError:
                suffix = "default"
        else:
            suffix = "default"
        
        return f"{config.table_name}_{suffix}"
    
    def get_all_shards(self, table_name: str) -> List[str]:
        """获取所有分片表名"""
        if table_name not in self._configs:
            return [table_name]
        
        config = self._configs[table_name]
        
        if config.strategy == ShardingStrategy.HASH:
            return [
                f"{table_name}_{i:02d}"
                for i in range(config.shard_count)
            ]
        elif config.strategy == ShardingStrategy.RANGE:
            return [
                f"{table_name}_{i:02d}"
                for i in range(len(config.ranges) + 1)
            ]
        elif config.strategy == ShardingStrategy.LIST:
            shards = [
                f"{table_name}_{name}"
                for name in config.list_values.keys()
            ]
            shards.append(f"{table_name}_default")
            return shards
        
        return [table_name]


class ShardManager:
    """分片管理器"""
    
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.router = ShardRouter()
    
    async def create_shards(self, config: ShardConfig):
        """创建分片表"""
        self.router.register(config)
        
        async with AsyncSession(self.engine) as session:
            # 获取原表结构
            source_ddl = await self._get_table_ddl(session, config.table_name)
            
            # 创建分片表
            for shard_name in self.router.get_all_shards(config.table_name):
                if shard_name == config.table_name:
                    continue
                
                # 修改表名
                shard_ddl = source_ddl.replace(
                    f'TABLE "{config.table_name}"',
                    f'TABLE "{shard_name}"'
                ).replace(
                    f"TABLE {config.table_name}",
                    f"TABLE {shard_name}"
                )
                
                try:
                    await session.execute(text(shard_ddl))
                    logger.info(f"创建分片表: {shard_name}")
                except Exception as e:
                    logger.error(f"创建分片表失败 {shard_name}: {e}")
            
            await session.commit()
    
    async def _get_table_ddl(
        self,
        session: AsyncSession,
        table_name: str
    ) -> str:
        """获取表DDL"""
        # 这是简化版本，实际需要根据数据库类型生成完整DDL
        query = text(f"""
            SELECT 
                'CREATE TABLE IF NOT EXISTS "' || :table_name || '" (' ||
                string_agg(
                    '"' || column_name || '" ' || 
                    data_type ||
                    CASE WHEN character_maximum_length IS NOT NULL 
                        THEN '(' || character_maximum_length || ')' 
                        ELSE '' 
                    END ||
                    CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END,
                    ', '
                ) || ')'
            FROM information_schema.columns 
            WHERE table_name = :table_name
        """)
        
        result = await session.execute(query, {"table_name": table_name})
        row = result.fetchone()
        return row[0] if row else ""
    
    async def migrate_data(
        self,
        config: ShardConfig,
        batch_size: int = 10000
    ):
        """迁移数据到分片"""
        async with AsyncSession(self.engine) as session:
            # 获取总行数
            count_query = text(f"SELECT COUNT(*) FROM {config.table_name}")
            result = await session.execute(count_query)
            total = result.scalar()
            
            logger.info(f"开始迁移数据, 总行数: {total}")
            
            offset = 0
            migrated = 0
            
            while offset < total:
                # 批量读取
                select_query = text(f"""
                    SELECT * FROM {config.table_name}
                    ORDER BY {config.shard_key}
                    LIMIT {batch_size} OFFSET {offset}
                """)
                
                result = await session.execute(select_query)
                rows = result.fetchall()
                columns = result.keys()
                
                # 按分片分组
                shard_data: Dict[str, List[Dict]] = defaultdict(list)
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    shard_key_value = row_dict[config.shard_key]
                    shard_name = self.router.route(config.table_name, shard_key_value)
                    shard_data[shard_name].append(row_dict)
                
                # 批量插入各分片
                for shard_name, data in shard_data.items():
                    if shard_name == config.table_name:
                        continue
                    
                    # 构建INSERT语句
                    cols = ", ".join(f'"{c}"' for c in columns)
                    placeholders = ", ".join(f":{c}" for c in columns)
                    insert_query = text(f"""
                        INSERT INTO {shard_name} ({cols})
                        VALUES ({placeholders})
                    """)
                    
                    for row_data in data:
                        await session.execute(insert_query, row_data)
                    
                    migrated += len(data)
                
                await session.commit()
                offset += batch_size
                logger.info(f"迁移进度: {migrated}/{total}")
            
            logger.info(f"数据迁移完成, 总计: {migrated} 行")


# ==================== 配置中心 ====================

@dataclass
class DatabaseConfig:
    """数据库配置"""
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    slow_query_threshold_ms: float = 1000


# ==================== 数据库优化管理器 ====================

class DatabaseOptimizer:
    """数据库优化管理器"""
    
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.index_analyzer = IndexAnalyzer(engine)
        self.slow_query_analyzer = SlowQueryAnalyzer(engine)
        self.shard_manager = ShardManager(engine)
    
    async def analyze_all_tables(self) -> Dict[str, Any]:
        """分析所有表"""
        async with AsyncSession(self.engine) as session:
            # 获取所有用户表
            query = text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            result = await session.execute(query)
            tables = [row[0] for row in result.fetchall()]
        
        analysis = {}
        for table in tables:
            analysis[table] = await self.index_analyzer.analyze_table(table)
        
        return analysis
    
    async def get_table_stats(self) -> List[Dict]:
        """获取表统计"""
        async with AsyncSession(self.engine) as session:
            query = text("""
                SELECT
                    relname as table_name,
                    n_live_tup as row_count,
                    n_dead_tup as dead_rows,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    pg_total_relation_size(relid) as total_size
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
            """)
            
            result = await session.execute(query)
            rows = result.fetchall()
            
            return [
                {
                    "table": row[0],
                    "rows": row[1],
                    "dead_rows": row[2],
                    "last_vacuum": row[3].isoformat() if row[3] else None,
                    "last_autovacuum": row[4].isoformat() if row[4] else None,
                    "last_analyze": row[5].isoformat() if row[5] else None,
                    "size_bytes": row[6]
                }
                for row in rows
            ]
    
    async def vacuum_analyze(self, table_name: str):
        """执行VACUUM ANALYZE"""
        async with self.engine.connect() as conn:
            # VACUUM需要在事务外执行
            await conn.execute(text("COMMIT"))
            await conn.execute(text(f"VACUUM ANALYZE {table_name}"))
            logger.info(f"VACUUM ANALYZE 完成: {table_name}")
    
    async def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        table_stats = await self.get_table_stats()
        slow_queries = self.slow_query_analyzer.get_top_slow_queries(limit=10)
        
        # 汇总建议
        recommendations = []
        
        # 检查死行过多的表
        for table in table_stats:
            if table["dead_rows"] > table["rows"] * 0.2:
                recommendations.append({
                    "type": "vacuum",
                    "table": table["table"],
                    "reason": f"死行比例过高 ({table['dead_rows']}/{table['rows']})"
                })
        
        # 检查慢查询
        for query in slow_queries[:5]:
            if query["avg_time_ms"] > 5000:
                recommendations.append({
                    "type": "slow_query",
                    "query_hash": query["hash"],
                    "avg_time_ms": query["avg_time_ms"],
                    "reason": "平均执行时间超过5秒"
                })
        
        return {
            "table_stats": table_stats,
            "slow_queries": slow_queries,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat()
        }


# ==================== 导出 ====================

__all__ = [
    # 索引分析
    "IndexType",
    "IndexInfo",
    "IndexRecommendation",
    "IndexAnalyzer",
    # 慢查询
    "SlowQuery",
    "SlowQueryAnalyzer",
    # 分片
    "ShardingStrategy",
    "ShardConfig",
    "ShardRouter",
    "ShardManager",
    # 配置
    "DatabaseConfig",
    # 管理器
    "DatabaseOptimizer",
]
