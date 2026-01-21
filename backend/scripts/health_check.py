#!/usr/bin/env python3
# 地方志数据智能管理系统 - 健康检查脚本
"""系统健康检查和诊断"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))


async def check_database():
    """检查数据库连接"""
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
        return True, "数据库连接正常"
    except Exception as e:
        return False, f"数据库连接失败: {e}"


async def check_redis():
    """检查Redis连接"""
    try:
        import redis.asyncio as redis
        
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(redis_url)
        await client.ping()
        await client.close()
        return True, "Redis连接正常"
    except Exception as e:
        return False, f"Redis连接失败: {e}"


def check_disk_space():
    """检查磁盘空间"""
    try:
        import shutil
        
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        usage_percent = (used / total) * 100
        
        if free_gb < 1:
            return False, f"磁盘空间不足: 剩余 {free_gb:.1f}GB"
        elif usage_percent > 90:
            return False, f"磁盘使用率过高: {usage_percent:.1f}%"
        else:
            return True, f"磁盘空间正常: 剩余 {free_gb:.1f}GB ({100-usage_percent:.1f}%可用)"
    except Exception as e:
        return False, f"磁盘检查失败: {e}"


def check_uploads_dir():
    """检查上传目录"""
    uploads_dir = Path("uploads")
    
    if not uploads_dir.exists():
        try:
            uploads_dir.mkdir(parents=True)
            return True, "上传目录已创建"
        except Exception as e:
            return False, f"创建上传目录失败: {e}"
    
    if not os.access(uploads_dir, os.W_OK):
        return False, "上传目录无写入权限"
    
    return True, "上传目录正常"


def check_logs_dir():
    """检查日志目录"""
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        try:
            logs_dir.mkdir(parents=True)
            return True, "日志目录已创建"
        except Exception as e:
            return False, f"创建日志目录失败: {e}"
    
    return True, "日志目录正常"


async def check_openai_api():
    """检查OpenAI API"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return False, "未配置OPENAI_API_KEY"
        
        # 简单验证key格式
        if not api_key.startswith("sk-"):
            return False, "OPENAI_API_KEY格式不正确"
        
        return True, "OpenAI API Key已配置"
    except Exception as e:
        return False, f"OpenAI检查失败: {e}"


def check_environment():
    """检查环境变量"""
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
    ]
    
    optional_vars = [
        "REDIS_URL",
        "OPENAI_API_KEY",
        "MINIO_ENDPOINT",
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        return False, f"缺少必要环境变量: {', '.join(missing)}"
    
    configured = []
    for var in optional_vars:
        if os.getenv(var):
            configured.append(var)
    
    return True, f"环境变量正常 (可选已配置: {len(configured)}/{len(optional_vars)})"


async def run_health_checks():
    """运行所有健康检查"""
    checks = [
        ("数据库", check_database()),
        ("Redis", check_redis()),
        ("OpenAI API", check_openai_api()),
        ("磁盘空间", asyncio.coroutine(lambda: check_disk_space())()),
        ("上传目录", asyncio.coroutine(lambda: check_uploads_dir())()),
        ("日志目录", asyncio.coroutine(lambda: check_logs_dir())()),
        ("环境变量", asyncio.coroutine(lambda: check_environment())()),
    ]
    
    results = []
    for name, check in checks:
        if asyncio.iscoroutine(check):
            ok, msg = await check
        else:
            ok, msg = check
        results.append((name, ok, msg))
    
    return results


def print_results(results):
    """打印检查结果"""
    print("=" * 60)
    print("地方志数据管理系统 - 健康检查报告")
    print("=" * 60)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    all_ok = True
    for name, ok, msg in results:
        status = "✓" if ok else "✗"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_ok = False
    
    print("-" * 60)
    if all_ok:
        print("✓ 系统状态: 正常")
        return 0
    else:
        print("⚠ 系统状态: 存在问题")
        return 1


async def main():
    """主函数"""
    results = await run_health_checks()
    exit_code = print_results(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
