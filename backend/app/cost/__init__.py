# 地方志数据智能管理系统 - 成本账本模块
"""资源成本追踪和预算管理"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger()


class CostCategory(str, Enum):
    """成本类别"""
    COMPUTE = "compute"      # 计算资源
    STORAGE = "storage"      # 存储
    NETWORK = "network"      # 网络
    DATABASE = "database"    # 数据库
    AI_API = "ai_api"        # AI API调用
    CDN = "cdn"              # CDN
    MONITORING = "monitoring"  # 监控
    OTHER = "other"          # 其他


class ResourceType(str, Enum):
    """资源类型"""
    # 计算
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    # 存储
    BLOCK_STORAGE = "block_storage"
    OBJECT_STORAGE = "object_storage"
    # 网络
    BANDWIDTH = "bandwidth"
    REQUESTS = "requests"
    # AI
    OPENAI_TOKENS = "openai_tokens"
    EMBEDDING_CALLS = "embedding_calls"


@dataclass
class CostEntry:
    """成本条目"""
    id: str
    category: CostCategory
    resource_type: ResourceType
    description: str
    amount: Decimal
    currency: str = "CNY"
    usage: float = 0  # 使用量
    unit: str = ""    # 单位
    unit_price: Decimal = Decimal("0")  # 单价
    timestamp: datetime = None
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "resource_type": self.resource_type.value,
            "description": self.description,
            "amount": str(self.amount),
            "currency": self.currency,
            "usage": self.usage,
            "unit": self.unit,
            "unit_price": str(self.unit_price),
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }


@dataclass
class Budget:
    """预算"""
    name: str
    amount: Decimal
    period: str = "monthly"  # daily/weekly/monthly/yearly
    category: Optional[CostCategory] = None
    alert_threshold: float = 0.8  # 80%告警
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "amount": str(self.amount),
            "period": self.period,
            "category": self.category.value if self.category else None,
            "alert_threshold": self.alert_threshold
        }


@dataclass
class CostReport:
    """成本报告"""
    period_start: datetime
    period_end: datetime
    total_cost: Decimal
    by_category: Dict[str, Decimal]
    by_resource: Dict[str, Decimal]
    top_items: List[CostEntry]
    budget_status: Dict[str, Dict]
    trends: Dict[str, List[float]]


class CostTracker:
    """成本追踪器"""
    
    def __init__(self, storage_path: str = "data/cost"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: List[CostEntry] = []
        self.budgets: List[Budget] = []
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        entries_file = self.storage_path / "entries.json"
        budgets_file = self.storage_path / "budgets.json"
        
        if entries_file.exists():
            try:
                with open(entries_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        item["category"] = CostCategory(item["category"])
                        item["resource_type"] = ResourceType(item["resource_type"])
                        item["amount"] = Decimal(item["amount"])
                        item["unit_price"] = Decimal(item["unit_price"])
                        item["timestamp"] = datetime.fromisoformat(item["timestamp"])
                        self.entries.append(CostEntry(**item))
            except Exception as e:
                logger.error("加载成本数据失败", error=str(e))
        
        if budgets_file.exists():
            try:
                with open(budgets_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        if item.get("category"):
                            item["category"] = CostCategory(item["category"])
                        item["amount"] = Decimal(item["amount"])
                        self.budgets.append(Budget(**item))
            except Exception as e:
                logger.error("加载预算数据失败", error=str(e))
    
    def _save_data(self):
        """保存数据"""
        entries_file = self.storage_path / "entries.json"
        budgets_file = self.storage_path / "budgets.json"
        
        with open(entries_file, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self.entries], f, ensure_ascii=False, indent=2)
        
        with open(budgets_file, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self.budgets], f, ensure_ascii=False, indent=2)
    
    def record_cost(self, entry: CostEntry):
        """记录成本"""
        self.entries.append(entry)
        self._save_data()
        
        logger.info(
            "记录成本",
            category=entry.category.value,
            amount=str(entry.amount),
            description=entry.description
        )
        
        # 检查预算
        self._check_budget_alerts(entry)
    
    def add_budget(self, budget: Budget):
        """添加预算"""
        self.budgets.append(budget)
        self._save_data()
        logger.info("添加预算", name=budget.name, amount=str(budget.amount))
    
    def get_period_cost(
        self,
        start: datetime,
        end: datetime,
        category: Optional[CostCategory] = None
    ) -> Decimal:
        """获取期间成本"""
        total = Decimal("0")
        
        for entry in self.entries:
            if start <= entry.timestamp <= end:
                if category is None or entry.category == category:
                    total += entry.amount
        
        return total
    
    def get_daily_cost(self, date: datetime = None) -> Decimal:
        """获取日成本"""
        date = date or datetime.now()
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return self.get_period_cost(start, end)
    
    def get_monthly_cost(self, year: int = None, month: int = None) -> Decimal:
        """获取月成本"""
        now = datetime.now()
        year = year or now.year
        month = month or now.month
        
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        
        return self.get_period_cost(start, end)
    
    def get_cost_by_category(
        self,
        start: datetime,
        end: datetime
    ) -> Dict[CostCategory, Decimal]:
        """按类别统计成本"""
        result = {cat: Decimal("0") for cat in CostCategory}
        
        for entry in self.entries:
            if start <= entry.timestamp <= end:
                result[entry.category] += entry.amount
        
        return result
    
    def _check_budget_alerts(self, entry: CostEntry):
        """检查预算告警"""
        for budget in self.budgets:
            if budget.category and budget.category != entry.category:
                continue
            
            # 获取当前周期成本
            now = datetime.now()
            if budget.period == "daily":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif budget.period == "weekly":
                start = now - timedelta(days=now.weekday())
                start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            elif budget.period == "monthly":
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:  # yearly
                start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
            current_cost = self.get_period_cost(start, now, budget.category)
            usage_percent = float(current_cost / budget.amount)
            
            if usage_percent >= budget.alert_threshold:
                logger.warning(
                    "预算告警",
                    budget=budget.name,
                    usage_percent=f"{usage_percent*100:.1f}%",
                    current=str(current_cost),
                    limit=str(budget.amount)
                )
    
    def generate_report(
        self,
        start: datetime,
        end: datetime
    ) -> CostReport:
        """生成成本报告"""
        # 按类别统计
        by_category = {}
        for cat in CostCategory:
            cost = self.get_period_cost(start, end, cat)
            if cost > 0:
                by_category[cat.value] = cost
        
        # 按资源类型统计
        by_resource = {}
        for entry in self.entries:
            if start <= entry.timestamp <= end:
                key = entry.resource_type.value
                by_resource[key] = by_resource.get(key, Decimal("0")) + entry.amount
        
        # Top项目
        period_entries = [e for e in self.entries if start <= e.timestamp <= end]
        top_items = sorted(period_entries, key=lambda x: x.amount, reverse=True)[:10]
        
        # 预算状态
        budget_status = {}
        for budget in self.budgets:
            current = self.get_period_cost(start, end, budget.category)
            budget_status[budget.name] = {
                "limit": str(budget.amount),
                "used": str(current),
                "percent": float(current / budget.amount) * 100,
                "remaining": str(budget.amount - current)
            }
        
        return CostReport(
            period_start=start,
            period_end=end,
            total_cost=sum(by_category.values(), Decimal("0")),
            by_category=by_category,
            by_resource=by_resource,
            top_items=top_items,
            budget_status=budget_status,
            trends={}  # TODO: 实现趋势分析
        )


# AI API成本追踪器
class AIAPICostTracker:
    """AI API成本追踪"""
    
    # 价格配置（每1000 tokens，单位：元）
    PRICING = {
        "gpt-4": {"input": 0.21, "output": 0.42},
        "gpt-4-turbo": {"input": 0.07, "output": 0.21},
        "gpt-3.5-turbo": {"input": 0.0035, "output": 0.007},
        "text-embedding-ada-002": {"input": 0.0007, "output": 0},
        "text-embedding-3-small": {"input": 0.00014, "output": 0},
    }
    
    def __init__(self, cost_tracker: CostTracker):
        self.cost_tracker = cost_tracker
    
    def track_completion(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[int] = None
    ):
        """追踪对话成本"""
        pricing = self.PRICING.get(model, self.PRICING["gpt-3.5-turbo"])
        
        input_cost = Decimal(str(input_tokens / 1000 * pricing["input"]))
        output_cost = Decimal(str(output_tokens / 1000 * pricing["output"]))
        total_cost = input_cost + output_cost
        
        entry = CostEntry(
            id=f"ai_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            category=CostCategory.AI_API,
            resource_type=ResourceType.OPENAI_TOKENS,
            description=f"OpenAI {model} API调用",
            amount=total_cost,
            usage=input_tokens + output_tokens,
            unit="tokens",
            unit_price=Decimal(str((pricing["input"] + pricing["output"]) / 2)),
            tags={
                "model": model,
                "input_tokens": str(input_tokens),
                "output_tokens": str(output_tokens),
                "user_id": str(user_id) if user_id else ""
            }
        )
        
        self.cost_tracker.record_cost(entry)
    
    def track_embedding(
        self,
        model: str,
        tokens: int
    ):
        """追踪嵌入成本"""
        pricing = self.PRICING.get(model, self.PRICING["text-embedding-ada-002"])
        cost = Decimal(str(tokens / 1000 * pricing["input"]))
        
        entry = CostEntry(
            id=f"emb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            category=CostCategory.AI_API,
            resource_type=ResourceType.EMBEDDING_CALLS,
            description=f"Embedding {model}",
            amount=cost,
            usage=tokens,
            unit="tokens",
            tags={"model": model}
        )
        
        self.cost_tracker.record_cost(entry)
