# 地方志数据智能管理系统 - 安全配置
"""安全相关配置"""

# JWT配置
JWT_CONFIG = {
    "secret_key": "your-secret-key-change-in-production",
    "algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
}

# 密码策略
PASSWORD_POLICY = {
    "min_length": 8,
    "max_length": 128,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digit": True,
    "require_special": False,
    "special_chars": "!@#$%^&*()_+-=[]{}|;:,.<>?",
}

# CORS配置
CORS_CONFIG = {
    "allow_origins": [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

# 速率限制
RATE_LIMIT_CONFIG = {
    "enabled": True,
    "default_limit": "100/minute",
    "limits": {
        "/api/auth/login": "10/minute",
        "/api/auth/register": "5/minute",
        "/api/ai/chat": "20/minute",
        "/api/documents": "200/minute",
    },
}

# API Key配置
API_KEY_CONFIG = {
    "header_name": "X-API-Key",
    "query_param": "api_key",
    "enabled": False,
}

# 文件上传安全
FILE_UPLOAD_CONFIG = {
    "max_size_mb": 50,
    "allowed_extensions": [
        ".txt", ".md", ".doc", ".docx",
        ".xls", ".xlsx", ".csv",
        ".pdf",
        ".jpg", ".jpeg", ".png", ".gif",
    ],
    "allowed_mimetypes": [
        "text/plain",
        "text/markdown",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
    ],
    "scan_virus": False,  # 需要配置ClamAV
}

# IP白名单/黑名单
IP_FILTER_CONFIG = {
    "enabled": False,
    "whitelist": [],
    "blacklist": [],
}

# 敏感数据脱敏
DATA_MASKING_CONFIG = {
    "enabled": True,
    "fields": {
        "email": lambda x: x[:3] + "***" + x[x.find("@"):] if "@" in x else "***",
        "phone": lambda x: x[:3] + "****" + x[-4:] if len(x) >= 11 else "***",
        "id_card": lambda x: x[:6] + "********" + x[-4:] if len(x) >= 18 else "***",
    },
}

# 安全头配置
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
}
