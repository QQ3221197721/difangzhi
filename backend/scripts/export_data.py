#!/usr/bin/env python3
# 地方志数据智能管理系统 - 数据导出脚本
"""导出数据为多种格式"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSession, engine
from app.models.models import Document, Category, DataStatus
from sqlalchemy import select


async def export_documents(
    output_path: str,
    format: str = "json",
    status: str = None,
    region: str = None
):
    """
    导出文档数据
    
    Args:
        output_path: 输出路径
        format: 格式 (json/csv/jsonl)
        status: 筛选状态
        region: 筛选地区
    """
    print("=" * 50)
    print("地方志数据管理系统 - 数据导出")
    print("=" * 50)
    print(f"输出: {output_path}")
    print(f"格式: {format}")
    print("-" * 50)
    
    async with AsyncSession(engine) as session:
        query = select(Document)
        
        if status:
            query = query.where(Document.status == DataStatus(status))
        if region:
            query = query.where(Document.region == region)
        
        result = await session.execute(query)
        documents = result.scalars().all()
        
        print(f"✓ 查询到 {len(documents)} 条文档")
        
        # 转换为字典
        data = []
        for doc in documents:
            item = {
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "region": doc.region,
                "year": doc.year,
                "tags": doc.tags or [],
                "source": doc.source,
                "author": doc.author,
                "ai_summary": doc.ai_summary,
                "ai_keywords": doc.ai_keywords or [],
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            data.append(item)
        
        # 输出
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        elif format == "jsonl":
            with open(output_file, "w", encoding="utf-8") as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        elif format == "csv":
            if data:
                with open(output_file, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    for item in data:
                        # 转换列表为字符串
                        item["tags"] = ",".join(item["tags"])
                        item["ai_keywords"] = ",".join(item["ai_keywords"])
                        writer.writerow(item)
        
        print(f"✓ 导出完成: {output_file}")


async def export_categories(output_path: str):
    """导出分类数据"""
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Category))
        categories = result.scalars().all()
        
        data = []
        for cat in categories:
            data.append({
                "id": cat.id,
                "name": cat.name,
                "code": cat.code,
                "level": cat.level,
                "parent_id": cat.parent_id,
                "category_type": cat.category_type,
                "description": cat.description,
                "sort_order": cat.sort_order,
            })
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 分类导出完成: {output_path} ({len(data)} 条)")


async def export_for_training(output_path: str):
    """导出用于模型训练的数据"""
    print("\n导出训练数据...")
    
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Document).where(Document.status == DataStatus.APPROVED)
        )
        documents = result.scalars().all()
        
        # 准备训练数据格式
        training_data = []
        for doc in documents:
            if doc.content:
                training_data.append({
                    "text": doc.content,
                    "title": doc.title,
                    "metadata": {
                        "region": doc.region,
                        "year": doc.year,
                        "source": doc.source
                    }
                })
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        print(f"✓ 训练数据导出完成: {output_file} ({len(training_data)} 条)")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="数据导出工具")
    parser.add_argument("--output", "-o", required=True, help="输出文件路径")
    parser.add_argument("--format", "-f", choices=["json", "csv", "jsonl"], default="json", help="输出格式")
    parser.add_argument("--type", choices=["documents", "categories", "training"], default="documents", help="数据类型")
    parser.add_argument("--status", help="筛选状态")
    parser.add_argument("--region", help="筛选地区")
    
    args = parser.parse_args()
    
    if args.type == "documents":
        asyncio.run(export_documents(
            args.output,
            format=args.format,
            status=args.status,
            region=args.region
        ))
    elif args.type == "categories":
        asyncio.run(export_categories(args.output))
    elif args.type == "training":
        asyncio.run(export_for_training(args.output))


if __name__ == "__main__":
    main()
