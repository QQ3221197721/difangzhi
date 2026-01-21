# 地方志数据智能管理系统 - 文件处理工具
"""文件操作、哈希计算、MIME类型检测等工具"""

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO, List, Optional, Union
from datetime import datetime

# 允许的文件类型
ALLOWED_EXTENSIONS = {
    'document': {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'},
    'spreadsheet': {'.xls', '.xlsx', '.csv'},
    'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'},
    'archive': {'.zip', '.rar', '.7z'},
}

# MIME类型映射
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.csv': 'text/csv',
    '.txt': 'text/plain',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.zip': 'application/zip',
}


def get_file_hash(file: Union[BinaryIO, bytes, str], algorithm: str = "md5") -> str:
    """
    计算文件哈希值
    
    Args:
        file: 文件对象、字节内容或文件路径
        algorithm: 哈希算法 (md5/sha1/sha256)
        
    Returns:
        哈希值字符串
    """
    hash_func = getattr(hashlib, algorithm)()
    
    if isinstance(file, str):
        # 文件路径
        with open(file, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
    elif isinstance(file, bytes):
        # 字节内容
        hash_func.update(file)
    else:
        # 文件对象
        file.seek(0)
        for chunk in iter(lambda: file.read(8192), b''):
            hash_func.update(chunk)
        file.seek(0)
    
    return hash_func.hexdigest()


def get_file_extension(filename: str) -> str:
    """
    获取文件扩展名
    
    Args:
        filename: 文件名
        
    Returns:
        扩展名（小写，带点）
    """
    if not filename:
        return ""
    
    return Path(filename).suffix.lower()


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    清理文件名，移除不安全字符
    
    Args:
        filename: 原始文件名
        max_length: 最大长度
        
    Returns:
        安全的文件名
    """
    if not filename:
        return "unnamed"
    
    # 获取扩展名
    ext = get_file_extension(filename)
    name = Path(filename).stem
    
    # 移除不安全字符
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    
    # 移除前导/尾随空白和点
    name = name.strip(' .')
    
    # 截断
    if len(name) + len(ext) > max_length:
        name = name[:max_length - len(ext)]
    
    if not name:
        name = "unnamed"
    
    return name + ext


def get_mime_type(filename: str) -> str:
    """
    获取文件MIME类型
    
    Args:
        filename: 文件名
        
    Returns:
        MIME类型字符串
    """
    ext = get_file_extension(filename)
    return MIME_TYPES.get(ext, 'application/octet-stream')


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
        
    Returns:
        格式化的大小字符串
    """
    if size_bytes < 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def is_allowed_file(
    filename: str,
    allowed_types: Optional[List[str]] = None
) -> bool:
    """
    检查文件类型是否允许
    
    Args:
        filename: 文件名
        allowed_types: 允许的类型列表 (document/spreadsheet/image/archive)
        
    Returns:
        是否允许
    """
    ext = get_file_extension(filename)
    
    if allowed_types is None:
        # 检查所有允许的类型
        all_extensions = set()
        for extensions in ALLOWED_EXTENSIONS.values():
            all_extensions.update(extensions)
        return ext in all_extensions
    
    allowed_extensions = set()
    for file_type in allowed_types:
        if file_type in ALLOWED_EXTENSIONS:
            allowed_extensions.update(ALLOWED_EXTENSIONS[file_type])
    
    return ext in allowed_extensions


def create_unique_filename(
    original_filename: str,
    prefix: Optional[str] = None
) -> str:
    """
    创建唯一文件名
    
    Args:
        original_filename: 原始文件名
        prefix: 文件名前缀
        
    Returns:
        唯一文件名
    """
    ext = get_file_extension(original_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    
    if prefix:
        return f"{prefix}_{timestamp}_{unique_id}{ext}"
    else:
        return f"{timestamp}_{unique_id}{ext}"


def get_file_info(file_path: str) -> dict:
    """
    获取文件详细信息
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件信息字典
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"error": "文件不存在"}
    
    stat = path.stat()
    
    return {
        "name": path.name,
        "stem": path.stem,
        "extension": path.suffix,
        "size": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "mime_type": get_mime_type(path.name),
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
    }


def ensure_directory(dir_path: str) -> bool:
    """
    确保目录存在
    
    Args:
        dir_path: 目录路径
        
    Returns:
        是否成功
    """
    try:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def list_files(
    directory: str,
    pattern: str = "*",
    recursive: bool = False
) -> List[str]:
    """
    列出目录下的文件
    
    Args:
        directory: 目录路径
        pattern: 文件匹配模式
        recursive: 是否递归
        
    Returns:
        文件路径列表
    """
    path = Path(directory)
    
    if not path.exists():
        return []
    
    if recursive:
        files = path.rglob(pattern)
    else:
        files = path.glob(pattern)
    
    return [str(f) for f in files if f.is_file()]


def get_storage_path(
    category: str,
    filename: str,
    base_path: str = "uploads"
) -> str:
    """
    生成存储路径
    
    Args:
        category: 文件分类
        filename: 文件名
        base_path: 基础路径
        
    Returns:
        完整存储路径
    """
    date_path = datetime.now().strftime("%Y/%m/%d")
    return os.path.join(base_path, category, date_path, filename)
