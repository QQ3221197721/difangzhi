"""
AI助手API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_verified_user
from app.models.models import User, ChronicleRecord, AIConversation
from app.models.schemas import (
    AIConversationRequest, AIConversationResponse, 
    SearchResult, APIResponse
)
from app.services.ai_assistant import AIAssistantService


router = APIRouter(prefix="/ai", tags=["AI助手"])


@router.post("/chat", response_model=AIConversationResponse)
async def chat_with_ai(
    request: AIConversationRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """
    与AI助手对话
    支持：
    - 数据查询问答
    - 数据分析建议
    - 报告生成
    - 操作指导
    """
    # 获取或创建会话
    session_id = request.session_id or uuid.uuid4()
    
    # 获取历史对话上下文
    history = []
    if request.session_id:
        result = await db.execute(
            select(AIConversation)
            .where(AIConversation.session_id == request.session_id)
            .order_by(AIConversation.created_at.desc())
            .limit(10)
        )
        history_records = result.scalars().all()
        history = [{"role": h.role, "content": h.content} for h in reversed(history_records)]
    
    # 获取相关数据上下文
    context_data = None
    if request.context_record_ids:
        result = await db.execute(
            select(ChronicleRecord)
            .where(ChronicleRecord.id.in_(request.context_record_ids))
            .limit(10)
        )
        records = result.scalars().all()
        context_data = [
            {
                "title": r.title,
                "region": r.region_city,
                "year": r.year,
                "work_category": r.work_category,
                "income": r.income,
                "summary": r.summary
            }
            for r in records
        ]
    
    # 调用AI服务
    ai_service = AIAssistantService()
    response = await ai_service.chat(
        message=request.message,
        history=history,
        context_data=context_data
    )
    
    # 保存用户消息
    user_message = AIConversation(
        user_id=current_user.id,
        session_id=session_id,
        role="user",
        content=request.message,
        context_records=request.context_record_ids
    )
    db.add(user_message)
    
    # 保存AI回复
    ai_message = AIConversation(
        user_id=current_user.id,
        session_id=session_id,
        role="assistant",
        content=response["message"],
        tokens_used=response.get("tokens_used"),
        model_used=response.get("model")
    )
    db.add(ai_message)
    
    await db.commit()
    
    # 获取相关记录推荐
    related_records = None
    if response.get("search_keywords"):
        search_result = await db.execute(
            select(ChronicleRecord)
            .where(
                ChronicleRecord.title.ilike(f"%{response['search_keywords'][0]}%")
            )
            .limit(5)
        )
        related = search_result.scalars().all()
        if related:
            related_records = [
                SearchResult(
                    id=r.id,
                    title=r.title,
                    content=r.content[:200] if r.content else None,
                    summary=r.summary,
                    region=r.region,
                    region_city=r.region_city,
                    year=r.year,
                    unit=r.unit,
                    person=r.person,
                    income=r.income,
                    work_category=r.work_category,
                    tags=r.tags or {},
                    confidence_score=r.confidence_score,
                    created_at=r.created_at
                )
                for r in related
            ]
    
    return AIConversationResponse(
        session_id=session_id,
        message=response["message"],
        suggestions=response.get("suggestions"),
        related_records=related_records
    )


@router.get("/sessions")
async def get_chat_sessions(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的对话会话列表"""
    result = await db.execute(
        select(AIConversation.session_id, AIConversation.created_at)
        .where(AIConversation.user_id == current_user.id)
        .group_by(AIConversation.session_id, AIConversation.created_at)
        .order_by(AIConversation.created_at.desc())
        .limit(20)
    )
    sessions = result.all()
    
    return {
        "sessions": [
            {"session_id": str(s[0]), "created_at": s[1].isoformat()}
            for s in sessions
        ]
    }


@router.get("/session/{session_id}")
async def get_session_history(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """获取指定会话的对话历史"""
    result = await db.execute(
        select(AIConversation)
        .where(
            AIConversation.session_id == session_id,
            AIConversation.user_id == current_user.id
        )
        .order_by(AIConversation.created_at.asc())
    )
    messages = result.scalars().all()
    
    return {
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    }


@router.post("/analyze-query")
async def analyze_query(
    query: str,
    current_user: User = Depends(get_current_verified_user)
):
    """分析用户查询意图"""
    ai_service = AIAssistantService()
    analysis = await ai_service.analyze_query_intent(query)
    
    return {
        "intent": analysis.get("intent"),
        "entities": analysis.get("entities"),
        "suggested_filters": analysis.get("suggested_filters"),
        "suggested_actions": analysis.get("suggested_actions")
    }


@router.post("/generate-report")
async def generate_report(
    record_ids: List[uuid.UUID],
    report_type: str = "summary",
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """生成数据报告"""
    result = await db.execute(
        select(ChronicleRecord).where(ChronicleRecord.id.in_(record_ids))
    )
    records = result.scalars().all()
    
    if not records:
        raise HTTPException(status_code=404, detail="未找到指定记录")
    
    # 准备数据
    data_context = [
        {
            "title": r.title,
            "region": r.region,
            "region_city": r.region_city,
            "year": r.year,
            "unit": r.unit,
            "person": r.person,
            "income": r.income,
            "work_category": r.work_category,
            "content": r.content[:500] if r.content else None
        }
        for r in records
    ]
    
    ai_service = AIAssistantService()
    report = await ai_service.generate_report(data_context, report_type)
    
    return {
        "report": report,
        "records_count": len(records),
        "report_type": report_type
    }


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db)
):
    """删除对话会话"""
    result = await db.execute(
        select(AIConversation).where(
            AIConversation.session_id == session_id,
            AIConversation.user_id == current_user.id
        )
    )
    messages = result.scalars().all()
    
    for msg in messages:
        await db.delete(msg)
    
    await db.commit()
    
    return APIResponse(success=True, message="会话已删除")
