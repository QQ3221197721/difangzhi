"""
地方志数据智能管理系统 - AI 搜索与助手 API
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models import User, Document, AIChat, DataStatus
from app.schemas.schemas import (
    AISearchQuery, AISearchResult, ChatMessage, ChatResponse,
    ChatHistory, DocumentListResponse, ResponseBase
)
from app.api.auth import get_current_active_user
from app.services.ai_service import ai_service

router = APIRouter(prefix="/ai", tags=["AI 智能"])


@router.post("/search", response_model=AISearchResult)
async def ai_search(
    query: AISearchQuery,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """AI 智能搜索"""
    # 使用 AI 服务进行语义搜索
    result = await ai_service.semantic_search(
        question=query.question,
        top_k=query.top_k,
        db=db
    )
    
    return AISearchResult(
        answer=result["answer"],
        sources=[DocumentListResponse.model_validate(doc) for doc in result["sources"]],
        confidence=result["confidence"]
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """AI 对话"""
    # 生成或使用会话 ID
    session_id = message.session_id or str(uuid.uuid4())
    
    # 获取历史对话
    history = []
    if message.session_id:
        result = await db.execute(
            select(AIChat)
            .where(AIChat.user_id == current_user.id, AIChat.session_id == session_id)
            .order_by(AIChat.created_at.asc())
            .limit(20)
        )
        history = [{"role": chat.role, "content": chat.content} for chat in result.scalars().all()]
    
    # 调用 AI 服务
    response = await ai_service.chat(
        message=message.content,
        history=history,
        user_id=current_user.id
    )
    
    # 保存对话记录
    user_chat = AIChat(
        user_id=current_user.id,
        session_id=session_id,
        role="user",
        content=message.content,
    )
    assistant_chat = AIChat(
        user_id=current_user.id,
        session_id=session_id,
        role="assistant",
        content=response["content"],
        tokens_used=response["tokens_used"],
    )
    db.add(user_chat)
    db.add(assistant_chat)
    await db.commit()
    
    return ChatResponse(
        session_id=session_id,
        content=response["content"],
        tokens_used=response["tokens_used"],
        created_at=datetime.utcnow()
    )


@router.get("/chat/history", response_model=List[ChatHistory])
async def get_chat_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的对话会话列表"""
    result = await db.execute(
        select(AIChat.session_id)
        .where(AIChat.user_id == current_user.id)
        .group_by(AIChat.session_id)
        .order_by(func.max(AIChat.created_at).desc())
        .limit(20)
    )
    sessions = result.scalars().all()
    
    histories = []
    for session_id in sessions:
        result = await db.execute(
            select(AIChat)
            .where(AIChat.user_id == current_user.id, AIChat.session_id == session_id)
            .order_by(AIChat.created_at.asc())
        )
        messages = [
            {"role": chat.role, "content": chat.content, "created_at": chat.created_at.isoformat()}
            for chat in result.scalars().all()
        ]
        histories.append(ChatHistory(session_id=session_id, messages=messages))
    
    return histories


@router.get("/chat/{session_id}", response_model=ChatHistory)
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """获取特定会话的对话历史"""
    result = await db.execute(
        select(AIChat)
        .where(AIChat.user_id == current_user.id, AIChat.session_id == session_id)
        .order_by(AIChat.created_at.asc())
    )
    chats = result.scalars().all()
    
    if not chats:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    messages = [
        {"role": chat.role, "content": chat.content, "created_at": chat.created_at.isoformat()}
        for chat in chats
    ]
    
    return ChatHistory(session_id=session_id, messages=messages)


@router.delete("/chat/{session_id}", response_model=ResponseBase)
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """删除对话会话"""
    await db.execute(
        AIChat.__table__.delete().where(
            AIChat.user_id == current_user.id,
            AIChat.session_id == session_id
        )
    )
    await db.commit()
    
    return ResponseBase(message="对话已删除")


@router.post("/summarize/{document_id}", response_model=ResponseBase)
async def summarize_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """为文档生成 AI 摘要"""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 生成摘要
    content = document.full_text or document.content
    if not content:
        raise HTTPException(status_code=400, detail="文档内容为空")
    
    summary = await ai_service.summarize(content)
    
    # 更新文档
    document.ai_summary = summary["summary"]
    document.ai_keywords = summary["keywords"]
    await db.commit()
    
    return ResponseBase(message="摘要生成成功", data={
        "summary": summary["summary"],
        "keywords": summary["keywords"]
    })
