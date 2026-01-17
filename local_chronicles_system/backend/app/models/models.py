"""
数据库模型定义
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TSVECTOR
from datetime import datetime
import uuid
import enum
from app.core.database import Base


class UserStatus(enum.Enum):
    """用户状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    PENDING_VERIFICATION = "pending_verification"


class UserRole(enum.Enum):
    """用户角色"""
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # 实名认证信息
    real_name = Column(String(50), nullable=True)
    id_card = Column(String(18), nullable=True, unique=True)  # 身份证号加密存储
    phone = Column(String(20), nullable=True)
    is_verified = Column(Boolean, default=False)
    verification_time = Column(DateTime, nullable=True)
    
    # 用户状态和角色
    status = Column(SQLEnum(UserStatus), default=UserStatus.PENDING_VERIFICATION)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    
    # 安全相关
    failed_login_attempts = Column(Integer, default=0)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(50), nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    locations = relationship("UserLocation", back_populates="user")
    uploads = relationship("FileUpload", back_populates="user")
    search_history = relationship("SearchHistory", back_populates="user")
    
    __table_args__ = (
        Index('ix_users_real_name', 'real_name'),
        Index('ix_users_status', 'status'),
    )


class UserLocation(Base):
    """用户位置记录表"""
    __tablename__ = "user_locations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)  # 精度（米）
    
    address = Column(String(500), nullable=True)  # 解析后的地址
    city = Column(String(100), nullable=True)
    province = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    
    ip_address = Column(String(50), nullable=True)
    device_info = Column(JSON, nullable=True)
    
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="locations")
    
    __table_args__ = (
        Index('ix_user_locations_user_id', 'user_id'),
        Index('ix_user_locations_recorded_at', 'recorded_at'),
    )


class Category(Base):
    """分类标签表"""
    __tablename__ = "categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)  # 分类名称
    level = Column(Integer, default=1)  # 层级：1=一级分类，2=二级分类
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 自关联
    parent = relationship("Category", remote_side=[id], backref="children")
    
    __table_args__ = (
        Index('ix_categories_name', 'name'),
        Index('ix_categories_parent_id', 'parent_id'),
        Index('ix_categories_level', 'level'),
    )


class ChronicleRecord(Base):
    """地方志数据记录表"""
    __tablename__ = "chronicle_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 基础信息
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)  # 原始内容
    summary = Column(Text, nullable=True)  # AI生成的摘要
    
    # 核心分类标签（一级分类）
    region = Column(String(200), nullable=True)  # 地区
    region_province = Column(String(100), nullable=True)
    region_city = Column(String(100), nullable=True)
    region_district = Column(String(100), nullable=True)
    
    year = Column(Integer, nullable=True)  # 年份
    unit = Column(String(200), nullable=True)  # 单位
    person = Column(String(200), nullable=True)  # 人物
    income = Column(Float, nullable=True)  # 收入
    income_range = Column(String(50), nullable=True)  # 收入范围
    work_category = Column(String(100), nullable=True)  # 工作类别
    
    # 扩展标签（JSON存储）
    tags = Column(JSONB, default=dict)  # 所有标签的JSON存储
    
    # 数值数据（用于分析）
    numeric_data = Column(JSONB, default=dict)
    
    # 全文搜索向量
    search_vector = Column(TSVECTOR, nullable=True)
    
    # 来源信息
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("file_uploads.id"), nullable=True)
    source_type = Column(String(50), nullable=True)  # ai_extracted, manual_upload
    
    # 数据质量
    confidence_score = Column(Float, default=1.0)  # AI提取置信度
    is_verified = Column(Boolean, default=False)  # 人工验证
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # 关系
    source_file = relationship("FileUpload", back_populates="records")
    record_categories = relationship("RecordCategory", back_populates="record")
    
    __table_args__ = (
        Index('ix_chronicle_records_region', 'region'),
        Index('ix_chronicle_records_year', 'year'),
        Index('ix_chronicle_records_work_category', 'work_category'),
        Index('ix_chronicle_records_region_city', 'region_city'),
        Index('ix_chronicle_records_search_vector', 'search_vector', postgresql_using='gin'),
        Index('ix_chronicle_records_tags', 'tags', postgresql_using='gin'),
    )


class RecordCategory(Base):
    """记录-分类关联表"""
    __tablename__ = "record_categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id = Column(UUID(as_uuid=True), ForeignKey("chronicle_records.id"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    
    confidence = Column(Float, default=1.0)  # 分类置信度
    source = Column(String(50), default="ai")  # ai, manual
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    record = relationship("ChronicleRecord", back_populates="record_categories")
    category = relationship("Category")
    
    __table_args__ = (
        Index('ix_record_categories_record_id', 'record_id'),
        Index('ix_record_categories_category_id', 'category_id'),
    )


class FileUpload(Base):
    """文件上传记录表"""
    __tablename__ = "file_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 文件信息
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, txt, doc, xlsx
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=True)  # SHA-256哈希
    
    # 处理状态
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    
    # AI处理结果
    extracted_text = Column(Text, nullable=True)
    ai_analysis_result = Column(JSONB, default=dict)
    records_count = Column(Integer, default=0)  # 提取的记录数
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="uploads")
    records = relationship("ChronicleRecord", back_populates="source_file")
    
    __table_args__ = (
        Index('ix_file_uploads_user_id', 'user_id'),
        Index('ix_file_uploads_status', 'status'),
        Index('ix_file_uploads_file_hash', 'file_hash'),
    )


class SearchHistory(Base):
    """搜索历史表"""
    __tablename__ = "search_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    query_text = Column(Text, nullable=True)  # 智能搜索的文本
    filters = Column(JSONB, default=dict)  # 筛选条件
    search_type = Column(String(50), nullable=False)  # ai_search, filter_search
    
    results_count = Column(Integer, default=0)
    execution_time_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="search_history")
    
    __table_args__ = (
        Index('ix_search_history_user_id', 'user_id'),
        Index('ix_search_history_created_at', 'created_at'),
    )


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    action = Column(String(100), nullable=False)  # login, logout, upload, search, export, etc.
    resource_type = Column(String(100), nullable=True)  # user, file, record, etc.
    resource_id = Column(String(100), nullable=True)
    
    details = Column(JSONB, default=dict)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    status = Column(String(50), default="success")  # success, failed
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_audit_logs_user_id', 'user_id'),
        Index('ix_audit_logs_action', 'action'),
        Index('ix_audit_logs_created_at', 'created_at'),
    )


class AIConversation(Base):
    """AI对话记录表"""
    __tablename__ = "ai_conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    session_id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    
    # 相关上下文
    context_records = Column(ARRAY(UUID(as_uuid=True)), default=list)  # 关联的记录ID
    
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_ai_conversations_user_id', 'user_id'),
        Index('ix_ai_conversations_session_id', 'session_id'),
        Index('ix_ai_conversations_created_at', 'created_at'),
    )
