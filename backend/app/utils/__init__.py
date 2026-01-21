# 地方志数据智能管理系统 - 工具模块
"""通用工具函数集合"""

from .text import (
    clean_text,
    extract_keywords,
    truncate_text,
    highlight_matches,
    normalize_whitespace,
    remove_html_tags,
    extract_numbers,
    extract_dates,
)
from .file import (
    get_file_hash,
    get_file_extension,
    sanitize_filename,
    get_mime_type,
    format_file_size,
    is_allowed_file,
    create_unique_filename,
)
from .datetime import (
    format_datetime,
    parse_datetime,
    get_date_range,
    time_ago,
    is_valid_date,
    get_current_timestamp,
)
from .crypto import (
    generate_token,
    hash_string,
    verify_hash,
    encrypt_data,
    decrypt_data,
    generate_random_string,
)
from .pagination import (
    paginate,
    PaginationParams,
    PaginatedResponse,
)
from .response import (
    success_response,
    error_response,
    paginated_response,
)

__all__ = [
    # text
    "clean_text",
    "extract_keywords",
    "truncate_text",
    "highlight_matches",
    "normalize_whitespace",
    "remove_html_tags",
    "extract_numbers",
    "extract_dates",
    # file
    "get_file_hash",
    "get_file_extension",
    "sanitize_filename",
    "get_mime_type",
    "format_file_size",
    "is_allowed_file",
    "create_unique_filename",
    # datetime
    "format_datetime",
    "parse_datetime",
    "get_date_range",
    "time_ago",
    "is_valid_date",
    "get_current_timestamp",
    # crypto
    "generate_token",
    "hash_string",
    "verify_hash",
    "encrypt_data",
    "decrypt_data",
    "generate_random_string",
    # pagination
    "paginate",
    "PaginationParams",
    "PaginatedResponse",
    # response
    "success_response",
    "error_response",
    "paginated_response",
]
