"""
地方志数据智能管理系统 - AI 服务
"""
import json
from typing import List, Dict, Any, Optional

import openai
from openai import AsyncOpenAI
import jieba
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.config import settings
from app.models import Document, DataStatus

logger = structlog.get_logger()


class AIService:
    """AI 服务 - 基于 OpenAI API"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        
        # 系统提示词
        self.system_prompt = """你是一个专业的地方志资料助手，专门帮助用户查询和理解中国各地的地方志文献资料。
你的职责包括：
1. 回答关于地方志内容的问题
2. 帮助用户查找相关的历史文献
3. 解释地方志中的专业术语和历史背景
4. 提供文献摘要和关键信息提取

请始终保持专业、准确，引用来源时需标明出处。如果不确定答案，请明确告知用户。"""
    
    async def chat(
        self,
        message: str,
        history: List[Dict[str, str]] = None,
        user_id: int = None
    ) -> Dict[str, Any]:
        """对话接口"""
        try:
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # 添加历史消息
            if history:
                messages.extend(history)
            
            # 添加当前消息
            messages.append({"role": "user", "content": message})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            return {
                "content": content,
                "tokens_used": tokens_used
            }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "content": f"抱歉，AI 服务暂时不可用：{str(e)}",
                "tokens_used": 0
            }
    
    async def semantic_search(
        self,
        question: str,
        top_k: int = 10,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """语义搜索"""
        try:
            # 1. 获取问题的嵌入向量
            question_embedding = await self._get_embedding(question)
            
            # 2. 从数据库查询有嵌入向量的文档
            result = await db.execute(
                select(Document)
                .where(Document.status == DataStatus.APPROVED)
                .where(Document.embedding != None)
                .limit(100)
            )
            documents = result.scalars().all()
            
            if not documents:
                # 如果没有嵌入向量，回退到关键词搜索
                keywords = self._extract_keywords(question)
                result = await db.execute(
                    select(Document)
                    .where(Document.status == DataStatus.APPROVED)
                    .where(
                        Document.title.ilike(f"%{keywords[0]}%") if keywords else True
                    )
                    .limit(top_k)
                )
                documents = result.scalars().all()
            else:
                # 3. 计算相似度并排序
                similarities = []
                for doc in documents:
                    if doc.embedding:
                        sim = self._cosine_similarity(question_embedding, doc.embedding)
                        similarities.append((doc, sim))
                
                similarities.sort(key=lambda x: x[1], reverse=True)
                documents = [doc for doc, _ in similarities[:top_k]]
            
            # 4. 使用 RAG 生成回答
            context = "\n\n".join([
                f"【{doc.title}】\n{doc.content or doc.ai_summary or ''}"
                for doc in documents[:5]
            ])
            
            answer = await self._generate_answer(question, context)
            
            return {
                "answer": answer,
                "sources": documents,
                "confidence": 0.85 if documents else 0.3
            }
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return {
                "answer": f"搜索过程中发生错误：{str(e)}",
                "sources": [],
                "confidence": 0
            }
    
    async def summarize(self, content: str) -> Dict[str, Any]:
        """生成摘要和关键词"""
        try:
            # 如果内容太长，截断
            if len(content) > 10000:
                content = content[:10000] + "..."
            
            prompt = f"""请对以下地方志文献内容进行分析，生成：
1. 一段200字以内的中文摘要
2. 5-10个关键词

文献内容：
{content}

请以JSON格式返回：
{{"summary": "摘要内容", "keywords": ["关键词1", "关键词2", ...]}}"""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的文献分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content
            # 尝试解析 JSON
            try:
                # 提取 JSON 部分
                start = result_text.find('{')
                end = result_text.rfind('}') + 1
                if start != -1 and end > start:
                    result = json.loads(result_text[start:end])
                else:
                    result = {"summary": result_text, "keywords": []}
            except json.JSONDecodeError:
                result = {"summary": result_text, "keywords": []}
            
            return result
        except Exception as e:
            logger.error(f"Summarize error: {e}")
            # 回退到简单的关键词提取
            keywords = self._extract_keywords(content)
            return {
                "summary": content[:200] + "..." if len(content) > 200 else content,
                "keywords": keywords[:10]
            }
    
    async def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入向量"""
        return await self._get_embedding(text)
    
    async def _get_embedding(self, text: str) -> List[float]:
        """内部方法：获取嵌入向量"""
        try:
            # 截断文本
            if len(text) > 8000:
                text = text[:8000]
            
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """基于上下文生成回答"""
        try:
            prompt = f"""基于以下地方志资料，回答用户的问题。如果资料中没有相关信息，请明确告知。

参考资料：
{context}

用户问题：{question}

请提供准确、详细的回答，并在适当时引用资料来源。"""
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Generate answer error: {e}")
            return f"生成回答时发生错误：{str(e)}"
    
    def _extract_keywords(self, text: str) -> List[str]:
        """使用 jieba 提取关键词"""
        import jieba.analyse
        keywords = jieba.analyse.extract_tags(text, topK=20)
        return keywords
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


# 单例实例
ai_service = AIService()
