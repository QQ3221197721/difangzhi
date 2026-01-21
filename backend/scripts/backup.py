#!/usr/bin/env python3
# 地方志数据智能管理系统 - 数据备份脚本
"""数据库和文件备份"""

import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# 配置
BACKUP_DIR = Path("backups")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "local_chronicles")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
UPLOADS_DIR = Path("uploads")
MAX_BACKUPS = 7  # 保留最近7个备份


def ensure_backup_dir():
    """确保备份目录存在"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ 备份目录: {BACKUP_DIR.absolute()}")


def backup_database():
    """备份PostgreSQL数据库"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"db_backup_{timestamp}.sql"
    
    # 设置环境变量（密码）
    env = os.environ.copy()
    if DB_PASSWORD:
        env["PGPASSWORD"] = DB_PASSWORD
    
    cmd = [
        "pg_dump",
        "-h", DB_HOST,
        "-p", str(DB_PORT),
        "-U", DB_USER,
        "-d", DB_NAME,
        "-f", str(backup_file),
        "--clean",
        "--if-exists"
    ]
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ 数据库备份成功: {backup_file}")
            # 压缩备份
            shutil.make_archive(
                str(backup_file).replace(".sql", ""),
                "gzip",
                BACKUP_DIR,
                backup_file.name
            )
            backup_file.unlink()  # 删除未压缩文件
            print(f"✓ 备份已压缩: {backup_file}.gz")
            return True
        else:
            print(f"✗ 数据库备份失败: {result.stderr}")
            return False
    except FileNotFoundError:
        print("✗ pg_dump命令不可用，请确保PostgreSQL客户端已安装")
        return False


def backup_uploads():
    """备份上传文件"""
    if not UPLOADS_DIR.exists():
        print("✓ 上传目录为空，跳过备份")
        return True
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"uploads_backup_{timestamp}"
    
    try:
        shutil.make_archive(str(backup_file), "gzip", UPLOADS_DIR)
        print(f"✓ 上传文件备份成功: {backup_file}.tar.gz")
        return True
    except Exception as e:
        print(f"✗ 上传文件备份失败: {e}")
        return False


def cleanup_old_backups():
    """清理旧备份"""
    backups = sorted(BACKUP_DIR.glob("*.gz"), key=lambda x: x.stat().st_mtime)
    
    if len(backups) > MAX_BACKUPS:
        to_delete = backups[:-MAX_BACKUPS]
        for backup in to_delete:
            backup.unlink()
            print(f"✓ 删除旧备份: {backup.name}")


def main():
    """主函数"""
    print("=" * 50)
    print("地方志数据管理系统 - 数据备份")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    ensure_backup_dir()
    
    db_ok = backup_database()
    files_ok = backup_uploads()
    
    cleanup_old_backups()
    
    print("-" * 50)
    if db_ok and files_ok:
        print("✓ 备份完成！")
    else:
        print("⚠ 部分备份失败，请检查错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
