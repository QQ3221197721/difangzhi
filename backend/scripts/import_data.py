#!/usr/bin/env python3
# 地方志数据智能管理系统 - 数据导入脚本
"""批量导入地方志数据"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSession, engine
from app.models.models import Document, DataStatus


async def import_from_csv(file_path: str, user_id: int = 1):
    """
    从CSV文件导入数据
    
    CSV格式：title,content,region,year,tags,source
    """
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"✗ 文件不存在: {file_path}")
        return 0
    
    imported = 0
    errors = []
    
    async with AsyncSession(engine) as session:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    tags = row.get('tags', '').split(',') if row.get('tags') else []
                    tags = [t.strip() for t in tags if t.strip()]
                    
                    year = int(row.get('year')) if row.get('year') else None
                    
                    document = Document(
                        title=row['title'],
                        content=row.get('content', ''),
                        region=row.get('region'),
                        year=year,
                        tags=tags,
                        source=row.get('source'),
                        uploader_id=user_id,
                        status=DataStatus.PENDING,
                        upload_type='import'
                    )
                    session.add(document)
                    imported += 1
                    
                except Exception as e:
                    errors.append(f"行 {reader.line_num}: {e}")
            
            await session.commit()
    
    print(f"✓ 导入完成: {imported} 条记录")
    if errors:
        print(f"⚠ 错误 ({len(errors)} 条):")
        for err in errors[:10]:  # 只显示前10个错误
            print(f"  - {err}")
    
    return imported


async def import_from_json(file_path: str, user_id: int = 1):
    """
    从JSON文件导入数据
    
    JSON格式：[{title, content, region, year, tags, source}, ...]
    """
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"✗ 文件不存在: {file_path}")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        data = [data]
    
    imported = 0
    
    async with AsyncSession(engine) as session:
        for item in data:
            try:
                document = Document(
                    title=item['title'],
                    content=item.get('content', ''),
                    region=item.get('region'),
                    year=item.get('year'),
                    tags=item.get('tags', []),
                    source=item.get('source'),
                    uploader_id=user_id,
                    status=DataStatus.PENDING,
                    upload_type='import'
                )
                session.add(document)
                imported += 1
            except Exception as e:
                print(f"⚠ 跳过: {e}")
        
        await session.commit()
    
    print(f"✓ 导入完成: {imported} 条记录")
    return imported


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='导入地方志数据')
    parser.add_argument('file', help='数据文件路径 (CSV/JSON)')
    parser.add_argument('--user-id', type=int, default=1, help='上传用户ID')
    
    args = parser.parse_args()
    
    file_path = Path(args.file)
    
    print("=" * 50)
    print("地方志数据管理系统 - 数据导入")
    print("=" * 50)
    print(f"文件: {file_path}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    if file_path.suffix.lower() == '.csv':
        asyncio.run(import_from_csv(args.file, args.user_id))
    elif file_path.suffix.lower() == '.json':
        asyncio.run(import_from_json(args.file, args.user_id))
    else:
        print(f"✗ 不支持的文件格式: {file_path.suffix}")
        sys.exit(1)


if __name__ == "__main__":
    main()
