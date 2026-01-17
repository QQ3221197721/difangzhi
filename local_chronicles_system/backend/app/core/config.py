"""
核心配置模块
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    # 基础配置
    APP_NAME: str = "地方志数据管理系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/local_chronicles"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600
    
    # JWT配置
    JWT_SECRET_KEY: str = "jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 实名认证API配置
    REAL_NAME_API_URL: str = "https://api.example.com/verify"
    REAL_NAME_API_KEY: str = ""
    
    # AI配置
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    AI_MAX_TOKENS: int = 4000
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "txt", "doc", "docx", "xls", "xlsx", "csv"]
    
    # 安全配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    RATE_LIMIT: str = "100/minute"
    
    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()


# 分类标签配置
CATEGORY_CONFIG = {
    "地区": {
        "type": "hierarchical",
        "levels": ["省", "市", "区县"],
        "examples": ["辽宁省", "葫芦岛市", "连山区"]
    },
    "年份": {
        "type": "range",
        "start": 2000,
        "end": 2050,
        "values": [str(year) for year in range(2000, 2051)]
    },
    "单位": {
        "type": "dynamic",
        "examples": ["政府机关", "企业", "事业单位", "社会组织"]
    },
    "人物": {
        "type": "dynamic",
        "examples": ["领导干部", "企业家", "学者", "劳动模范"]
    },
    "收入": {
        "type": "range_numeric",
        "unit": "万元",
        "ranges": ["0-10", "10-50", "50-100", "100-500", "500+"]
    },
    "工作类别": {
        "type": "enumeration",
        "values": ["农业", "工业", "服务业", "科技", "教育", "医疗", "金融", "交通", "建筑", "其他"]
    }
}
