#!/usr/bin/env python3
# 地方志数据智能管理系统 - 向量化脚本
"""批量生成文档向量并建立索引"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSession, engine
from app.models.models import Document, DataStatus
from app.inference import (
    EmbeddingService, EmbeddingConfig, EmbeddingBackend,
    FAISSVectorStore
)
from sqlalchemy import select, update


async def vectorize_documents(
    batch_size: int = 32,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    force: bool = False
):
    """
    批量向量化文档
    
    Args:
        batch_size: 批处理大小
        model_name: 嵌入模型名称
        force: 是否强制重新向量化
    """
    print("=" * 60)
    print("地方志数据管理系统 - 文档向量化")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"模型: {model_name}")
    print(f"批大小: {batch_size}")
    print("-" * 60)
    
    # 初始化嵌入服务
    config = EmbeddingConfig(
        backend=EmbeddingBackend.SENTENCE_TRANSFORMERS,
        model_name=model_name,
        dimension=384,
        batch_size=batch_size
    )
    embedding_service = EmbeddingService(config)
    await embedding_service.initialize()
    print("✓ 嵌入模型加载完成")
    
    # 初始化向量存储
    vector_store = FAISSVectorStore(
        dimension=config.dimension,
        index_path="vectors/documents"
    )
    await vector_store.initialize()
    print("✓ 向量存储初始化完成")
    
    # 查询需要向量化的文档
    async with AsyncSession(engine) as session:
        if force:
            query = select(Document).where(Document.status == DataStatus.APPROVED)
        else:
            query = select(Document).where(
                Document.status == DataStatus.APPROVED,
                Document.embedding == None
            )
        
        result = await session.execute(query)
        documents = result.scalars().all()
        
        total = len(documents)
        print(f"✓ 待处理文档: {total} 条")
        
        if total == 0:
            print("没有需要向量化的文档")
            return
        
        # 批量处理
        processed = 0
        errors = 0
        
        for i in range(0, total, batch_size):
            batch = documents[i:i+batch_size]
            
            # 准备文本
            texts = []
            ids = []
            metadata = []
            
            for doc in batch:
                content = doc.content or doc.ai_summary or doc.title
                if content:
                    texts.append(content)
                    ids.append(str(doc.id))
                    metadata.append({
                        "title": doc.title,
                        "region": doc.region or "",
                        "year": doc.year or 0,
                        "content": content[:500]  # 截断存储
                    })
            
            if not texts:
                continue
            
            try:
                # 生成嵌入
                embeddings = await embedding_service.embed_batch(texts)
                
                # 添加到向量库
                await vector_store.add(ids, embeddings, metadata)
                
                # 更新数据库
                for j, doc in enumerate(batch):
                    if j < len(embeddings):
                        doc.embedding = embeddings[j]
                
                await session.commit()
                processed += len(texts)
                
            except Exception as e:
                errors += len(batch)
                print(f"✗ 批次处理失败: {e}")
            
            # 进度
            progress = (i + len(batch)) / total * 100
            print(f"  进度: {progress:.1f}% ({processed}/{total})")
        
        # 保存向量索引
        await vector_store.save()
        print("✓ 向量索引已保存")
        
        print("-" * 60)
        print(f"✓ 向量化完成: 成功 {processed} 条, 失败 {errors} 条")


async def build_search_index():
    """构建全文搜索索引"""
    print("\n构建全文搜索索引...")
    
    async with AsyncSession(engine) as session:
        # 更新PostgreSQL全文搜索向量
        await session.execute("""
            UPDATE documents 
            SET search_vector = to_tsvector('simple', 
                coalesce(title, '') || ' ' || 
                coalesce(content, '') || ' ' || 
                coalesce(ai_summary, '')
            )
            WHERE status = 'approved'
        """)
        await session.commit()
    
    print("✓ 全文搜索索引构建完成")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="文档向量化工具")
    parser.add_argument("--batch-size", type=int, default=32, help="批处理大小")
    parser.add_argument("--model", default="paraphrase-multilingual-MiniLM-L12-v2", help="嵌入模型")
    parser.add_argument("--force", action="store_true", help="强制重新向量化")
    parser.add_argument("--fts", action="store_true", help="同时构建全文索引")
    
    args = parser.parse_args()
    
    asyncio.run(vectorize_documents(
        batch_size=args.batch_size,
        model_name=args.model,
        force=args.force
    ))
    
    if args.fts:
        asyncio.run(build_search_index())


if __name__ == "__main__":
    main()
