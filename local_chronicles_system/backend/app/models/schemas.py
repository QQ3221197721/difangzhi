"""
Pydantic 数据模式定义
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ==================== 认证相关 ====================

class UserRegister(BaseModel):
    """用户注册"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('两次密码不一致')
        return v


class UserLogin(BaseModel):
    """用户登录"""
    username: str
    password: str
    location: Optional[Dict[str, float]] = None  # {latitude, longitude}


class RealNameVerification(BaseModel):
    """实名认证"""
    real_name: str = Field(..., min_length=2, max_length=50)
    id_card: str = Field(..., min_length=18, max_length=18)
    phone: str = Field(..., min_length=11, max_length=11)


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """用户响应"""
    id: UUID
    username: str
    email: str
    real_name: Optional[str] = None
    is_verified: bool
    role: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserProfile(BaseModel):
    """用户资料"""
    id: UUID
    username: str
    email: str
    real_name_masked: Optional[str] = None
    phone_masked: Optional[str] = None
    is_verified: bool
    role: str
    last_login_at: Optional[datetime] = None


# ==================== 位置相关 ====================

class LocationData(BaseModel):
    """位置数据"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None
    address: Optional[str] = None


class LocationResponse(BaseModel):
    """位置响应"""
    id: UUID
    latitude: float
    longitude: float
    address: Optional[str]
    city: Optional[str]
    province: Optional[str]
    recorded_at: datetime
    
    class Config:
        from_attributes = True


# ==================== 文件上传相关 ====================

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    id: UUID
    original_filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class FileProcessingStatus(BaseModel):
    """文件处理状态"""
    id: UUID
    status: str
    records_count: int
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None


class ManualDataUpload(BaseModel):
    """手动上传数据"""
    title: str = Field(..., max_length=500)
    content: Optional[str] = None
    region: Optional[str] = None
    region_province: Optional[str] = None
    region_city: Optional[str] = None
    region_district: Optional[str] = None
    year: Optional[int] = Field(None, ge=2000, le=2050)
    unit: Optional[str] = None
    person: Optional[str] = None
    income: Optional[float] = None
    work_category: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    numeric_data: Optional[Dict[str, Any]] = None


class BatchDataUpload(BaseModel):
    """批量数据上传"""
    records: List[ManualDataUpload]


# ==================== 分类标签相关 ====================

class CategoryCreate(BaseModel):
    """创建分类"""
    name: str = Field(..., max_length=100)
    level: int = Field(default=1, ge=1, le=2)
    parent_id: Optional[UUID] = None
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    """分类响应"""
    id: UUID
    name: str
    level: int
    parent_id: Optional[UUID]
    description: Optional[str]
    children: List['CategoryResponse'] = []
    
    class Config:
        from_attributes = True


CategoryResponse.model_rebuild()


class CategoryTree(BaseModel):
    """分类树"""
    categories: List[CategoryResponse]


# ==================== 搜索相关 ====================

class SearchTypeEnum(str, Enum):
    """搜索类型"""
    AI_SEARCH = "ai_search"
    FILTER_SEARCH = "filter_search"


class FilterCondition(BaseModel):
    """筛选条件"""
    region: Optional[str] = None
    region_province: Optional[str] = None
    region_city: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    unit: Optional[str] = None
    person: Optional[str] = None
    income_min: Optional[float] = None
    income_max: Optional[float] = None
    work_category: Optional[str] = None
    tags: Optional[Dict[str, List[str]]] = None


class AISearchRequest(BaseModel):
    """AI智能搜索请求"""
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=50, ge=1, le=500)


class FilterSearchRequest(BaseModel):
    """筛选搜索请求"""
    filters: FilterCondition
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class SearchResult(BaseModel):
    """搜索结果"""
    id: UUID
    title: str
    content: Optional[str]
    summary: Optional[str]
    region: Optional[str]
    region_city: Optional[str]
    year: Optional[int]
    unit: Optional[str]
    person: Optional[str]
    income: Optional[float]
    work_category: Optional[str]
    tags: Dict[str, Any]
    confidence_score: float
    created_at: datetime
    
    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResult]
    total: int
    page: int
    page_size: int
    search_type: str
    execution_time_ms: int


# ==================== 数据分析相关 ====================

class AnalysisTypeEnum(str, Enum):
    """分析类型"""
    SUMMARY = "summary"
    TREND = "trend"
    COMPARISON = "comparison"
    DISTRIBUTION = "distribution"
    CORRELATION = "correlation"


class AnalysisRequest(BaseModel):
    """数据分析请求"""
    record_ids: List[UUID]
    analysis_type: AnalysisTypeEnum
    group_by: Optional[str] = None
    metrics: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None


class VisualizationTypeEnum(str, Enum):
    """可视化类型"""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TABLE = "table"


class VisualizationRequest(BaseModel):
    """可视化请求"""
    record_ids: List[UUID]
    chart_type: VisualizationTypeEnum
    x_field: str
    y_field: str
    group_field: Optional[str] = None
    title: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    """分析响应"""
    analysis_type: str
    data: Dict[str, Any]
    summary: str
    charts: Optional[List[Dict[str, Any]]] = None


class VisualizationResponse(BaseModel):
    """可视化响应"""
    chart_type: str
    image_base64: Optional[str] = None
    plot_data: Optional[Dict[str, Any]] = None
    title: str


# ==================== AI助手相关 ====================

class AIMessage(BaseModel):
    """AI消息"""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class AIConversationRequest(BaseModel):
    """AI对话请求"""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[UUID] = None
    context_record_ids: Optional[List[UUID]] = None


class AIConversationResponse(BaseModel):
    """AI对话响应"""
    session_id: UUID
    message: str
    suggestions: Optional[List[str]] = None
    related_records: Optional[List[SearchResult]] = None


# ==================== 通用响应 ====================

class APIResponse(BaseModel):
    """API通用响应"""
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
