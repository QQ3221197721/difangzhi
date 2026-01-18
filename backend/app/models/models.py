"""
地方志数据智能管理系统 - 数据模型
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, Float, JSON, Enum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """用户角色"""
    ADMIN = "admin"          # 管理员
    EDITOR = "editor"        # 编辑
    VIEWER = "viewer"        # 查看者
    UPLOADER = "uploader"    # 上传者


class DataStatus(str, enum.Enum):
    """数据状态"""
    PENDING = "pending"      # 待审核
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已拒绝
    ARCHIVED = "archived"    # 已归档


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    real_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="真实姓名")
    id_card: Mapped[Optional[str]] = mapped_column(String(18), comment="身份证号")
    phone: Mapped[Optional[str]] = mapped_column(String(20), comment="手机号")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, comment="实名认证状态")
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_location: Mapped[Optional[str]] = mapped_column(JSON, comment="最后位置信息")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    documents = relationship("Document", back_populates="uploader")
    login_logs = relationship("LoginLog", back_populates="user")
    
    __table_args__ = (
        Index("ix_users_real_name", "real_name"),
    )


class LoginLog(Base):
    """登录日志表"""
    __tablename__ = "login_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    location: Mapped[Optional[str]] = mapped_column(JSON, comment="登录位置")
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    login_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_success: Mapped[bool] = mapped_column(Boolean, default=True)
    fail_reason: Mapped[Optional[str]] = mapped_column(String(200))
    
    user = relationship("User", back_populates="login_logs")


class Category(Base):
    """分类标签表（支持多级）"""
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, comment="层级：1=一级，2=二级")
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"))
    category_type: Mapped[str] = mapped_column(String(50), comment="分类类型：region/year/person/event/other")
    description: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 自关联
    parent = relationship("Category", remote_side=[id], backref="children")
    
    __table_args__ = (
        Index("ix_categories_type_level", "category_type", "level"),
    )


class Document(Base):
    """文档/地方志数据表"""
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    content: Mapped[Optional[str]] = mapped_column(Text, comment="文档内容/摘要")
    full_text: Mapped[Optional[str]] = mapped_column(Text, comment="全文内容")
    source: Mapped[Optional[str]] = mapped_column(String(200), comment="来源")
    author: Mapped[Optional[str]] = mapped_column(String(100), comment="作者")
    publish_date: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="发布/记录日期")
    
    # 文件信息
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_name: Mapped[Optional[str]] = mapped_column(String(200))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    
    # 分类标签
    region: Mapped[Optional[str]] = mapped_column(String(100), comment="地区")
    year: Mapped[Optional[int]] = mapped_column(Integer, comment="年份")
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), default=list)
    
    # AI 处理结果
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, comment="AI摘要")
    ai_keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), comment="AI提取关键词")
    embedding: Mapped[Optional[List[float]]] = mapped_column(ARRAY(Float), comment="向量嵌入")
    
    # 全文搜索向量
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)
    
    # 状态
    status: Mapped[DataStatus] = mapped_column(Enum(DataStatus), default=DataStatus.PENDING)
    upload_type: Mapped[str] = mapped_column(String(20), default="file", comment="上传类型：file/manual")
    
    # 元数据
    uploader_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    reviewer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    review_comment: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    uploader = relationship("User", foreign_keys=[uploader_id], back_populates="documents")
    categories = relationship("DocumentCategory", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_documents_region_year", "region", "year"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),
    )


class DocumentCategory(Base):
    """文档-分类关联表"""
    __tablename__ = "document_categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"))
    
    document = relationship("Document", back_populates="categories")
    category = relationship("Category")
    
    __table_args__ = (
        UniqueConstraint("document_id", "category_id", name="uq_document_category"),
    )


class AIChat(Base):
    """AI 对话记录表"""
    __tablename__ = "ai_chats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    session_id: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20), comment="user/assistant/system")
    content: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_ai_chats_user_session", "user_id", "session_id"),
    )


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50), comment="操作类型")
    resource_type: Mapped[str] = mapped_column(String(50), comment="资源类型")
    resource_id: Mapped[Optional[int]] = mapped_column(Integer)
    detail: Mapped[Optional[str]] = mapped_column(JSON, comment="操作详情")
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_operation_logs_user_action", "user_id", "action"),
        Index("ix_operation_logs_created_at", "created_at"),
    )
