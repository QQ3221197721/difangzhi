"""
地方志数据智能管理系统 - Pydantic 模式
"""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from app.models.models import UserRole, DataStatus


# ==================== 通用响应 ====================

class ResponseBase(BaseModel):
    """统一响应基类"""
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None


class PaginatedResponse(ResponseBase):
    """分页响应"""
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0


# ==================== 用户相关 ====================

class UserBase(BaseModel):
    """用户基础模式"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    real_name: str = Field(..., min_length=2, max_length=50)
    phone: Optional[str] = None


class UserCreate(UserBase):
    """用户创建模式"""
    password: str = Field(..., min_length=6, max_length=100)
    id_card: Optional[str] = Field(None, max_length=18)


class UserUpdate(BaseModel):
    """用户更新模式"""
    real_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """用户响应模式"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime


class UserLogin(BaseModel):
    """用户登录模式"""
    username: str
    password: str
    location: Optional[Dict[str, float]] = Field(None, description="位置信息 {latitude, longitude}")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LocationUpdate(BaseModel):
    """位置更新"""
    latitude: float
    longitude: float
    address: Optional[str] = None


# ==================== 分类标签 ====================

class CategoryBase(BaseModel):
    """分类基础模式"""
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=50)
    category_type: str = Field(..., description="分类类型：region/year/person/event/other")
    description: Optional[str] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    """分类创建模式"""
    parent_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    """分类更新模式"""
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    """分类响应模式"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    level: int
    parent_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    children: List["CategoryResponse"] = []


# ==================== 文档相关 ====================

class DocumentBase(BaseModel):
    """文档基础模式"""
    title: str = Field(..., max_length=500)
    content: Optional[str] = None
    source: Optional[str] = None
    author: Optional[str] = None
    region: Optional[str] = None
    year: Optional[int] = None
    tags: List[str] = []


class DocumentCreate(DocumentBase):
    """文档创建模式（手动上传）"""
    category_ids: List[int] = []
    publish_date: Optional[datetime] = None


class DocumentUpdate(BaseModel):
    """文档更新模式"""
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    author: Optional[str] = None
    region: Optional[str] = None
    year: Optional[int] = None
    tags: Optional[List[str]] = None
    category_ids: Optional[List[int]] = None
    status: Optional[DataStatus] = None


class DocumentResponse(DocumentBase):
    """文档响应模式"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    full_text: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_keywords: Optional[List[str]] = None
    status: DataStatus
    upload_type: str
    uploader_id: int
    view_count: int
    download_count: int
    created_at: datetime
    updated_at: datetime
    categories: List[CategoryResponse] = []


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    content: Optional[str] = None
    source: Optional[str] = None
    region: Optional[str] = None
    year: Optional[int] = None
    status: DataStatus
    view_count: int
    created_at: datetime


class DocumentReview(BaseModel):
    """文档审核"""
    status: DataStatus
    comment: Optional[str] = None


# ==================== 搜索相关 ====================

class SearchQuery(BaseModel):
    """搜索查询"""
    keyword: Optional[str] = None
    region: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    category_ids: List[int] = []
    tags: List[str] = []
    status: Optional[DataStatus] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = "created_at"
    sort_order: str = "desc"


class AISearchQuery(BaseModel):
    """AI 智能搜索"""
    question: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(10, ge=1, le=50)


class SearchResult(BaseModel):
    """搜索结果"""
    documents: List[DocumentListResponse]
    total: int
    page: int
    page_size: int
    pages: int
    keywords: List[str] = []


class AISearchResult(BaseModel):
    """AI 搜索结果"""
    answer: str
    sources: List[DocumentListResponse]
    confidence: float


# ==================== AI 聊天 ====================

class ChatMessage(BaseModel):
    """聊天消息"""
    content: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    content: str
    tokens_used: int
    created_at: datetime


class ChatHistory(BaseModel):
    """聊天历史"""
    session_id: str
    messages: List[Dict[str, Any]]


# ==================== 数据分析 ====================

class AnalyticsQuery(BaseModel):
    """数据分析查询"""
    metric: str = Field(..., description="指标类型")
    group_by: Optional[str] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    filters: Dict[str, Any] = {}


class AnalyticsResult(BaseModel):
    """数据分析结果"""
    metric: str
    data: List[Dict[str, Any]]
    chart_type: str
    summary: Dict[str, Any] = {}


# ==================== 文件上传 ====================

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    file_name: str
    file_size: int
    file_type: str
    upload_url: Optional[str] = None
    task_id: Optional[str] = None


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str
    progress: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None


# 更新前向引用
CategoryResponse.model_rebuild()
