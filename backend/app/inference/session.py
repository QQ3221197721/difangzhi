# 地方志数据智能管理系统 - 会话管理器
"""多轮对话管理、上下文压缩、会话持久化"""

import asyncio
import json
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
import structlog

logger = structlog.get_logger()


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"


@dataclass
class Message:
    """消息"""
    role: MessageRole
    content: str
    timestamp: datetime = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "token_count": self.token_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
            token_count=data.get("token_count", 0)
        )


@dataclass
class SessionConfig:
    """会话配置"""
    max_history_messages: int = 50
    max_context_tokens: int = 4000
    compression_threshold: int = 3000
    auto_summarize: bool = True
    persist_enabled: bool = True
    ttl_hours: int = 24
    # 上下文窗口管理
    sliding_window_size: int = 20
    important_message_boost: float = 2.0


@dataclass  
class ConversationSummary:
    """对话摘要"""
    content: str
    message_range: Tuple[int, int]  # 摘要覆盖的消息范围
    created_at: datetime = None
    token_count: int = 0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now()


@dataclass
class Session:
    """会话"""
    id: str
    user_id: Optional[int] = None
    messages: List[Message] = field(default_factory=list)
    summaries: List[ConversationSummary] = field(default_factory=list)
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = None
    updated_at: datetime = None
    total_tokens: int = 0
    
    def __post_init__(self):
        now = datetime.now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
    
    def add_message(self, role: MessageRole, content: str, **kwargs) -> Message:
        """添加消息"""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = datetime.now()
        self.total_tokens += msg.token_count
        return msg
    
    def get_recent_messages(self, n: int) -> List[Message]:
        """获取最近n条消息"""
        return self.messages[-n:] if n > 0 else []
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "summaries": [
                {
                    "content": s.content,
                    "message_range": s.message_range,
                    "created_at": s.created_at.isoformat(),
                    "token_count": s.token_count
                }
                for s in self.summaries
            ],
            "system_prompt": self.system_prompt,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "total_tokens": self.total_tokens
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Session":
        session = cls(
            id=data["id"],
            user_id=data.get("user_id"),
            system_prompt=data.get("system_prompt"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            total_tokens=data.get("total_tokens", 0)
        )
        
        session.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        session.summaries = [
            ConversationSummary(
                content=s["content"],
                message_range=tuple(s["message_range"]),
                created_at=datetime.fromisoformat(s.get("created_at", datetime.now().isoformat())),
                token_count=s.get("token_count", 0)
            )
            for s in data.get("summaries", [])
        ]
        
        return session


class TokenCounter:
    """Token计数器"""
    
    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
        self._encoder = None
    
    def _get_encoder(self):
        if self._encoder is None:
            try:
                import tiktoken
                self._encoder = tiktoken.encoding_for_model(self.model)
            except Exception:
                self._encoder = "simple"
        return self._encoder
    
    def count(self, text: str) -> int:
        """计算token数"""
        encoder = self._get_encoder()
        if encoder == "simple":
            # 简单估算：中文约1.5字/token，英文约4字符/token
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 1.5 + other_chars / 4)
        return len(encoder.encode(text))
    
    def count_messages(self, messages: List[Message]) -> int:
        """计算消息列表的token数"""
        total = 0
        for msg in messages:
            if msg.token_count > 0:
                total += msg.token_count
            else:
                total += self.count(msg.content) + 4  # 加上role等开销
        return total


class ContextCompressor:
    """上下文压缩器"""
    
    def __init__(self, summarize_fn: Optional[Callable] = None):
        self.summarize_fn = summarize_fn
    
    async def compress(
        self,
        messages: List[Message],
        target_tokens: int,
        token_counter: TokenCounter
    ) -> Tuple[List[Message], Optional[ConversationSummary]]:
        """压缩上下文"""
        current_tokens = token_counter.count_messages(messages)
        
        if current_tokens <= target_tokens:
            return messages, None
        
        # 策略1：保留最近消息，摘要旧消息
        if self.summarize_fn and len(messages) > 6:
            # 保留最近的消息
            keep_recent = 6
            to_summarize = messages[:-keep_recent]
            recent = messages[-keep_recent:]
            
            # 生成摘要
            summary_text = await self._summarize_messages(to_summarize)
            summary = ConversationSummary(
                content=summary_text,
                message_range=(0, len(to_summarize)),
                token_count=token_counter.count(summary_text)
            )
            
            # 创建摘要消息
            summary_msg = Message(
                role=MessageRole.SYSTEM,
                content=f"[对话历史摘要]\n{summary_text}",
                token_count=summary.token_count
            )
            
            return [summary_msg] + recent, summary
        
        # 策略2：简单截断
        result = []
        total = 0
        for msg in reversed(messages):
            msg_tokens = msg.token_count or token_counter.count(msg.content)
            if total + msg_tokens > target_tokens:
                break
            result.insert(0, msg)
            total += msg_tokens
        
        return result, None
    
    async def _summarize_messages(self, messages: List[Message]) -> str:
        """摘要消息"""
        if self.summarize_fn:
            text = "\n".join([
                f"{m.role.value}: {m.content[:200]}"
                for m in messages
            ])
            return await self.summarize_fn(text)
        
        # 默认：简单提取关键信息
        key_points = []
        for msg in messages:
            if msg.role == MessageRole.USER:
                key_points.append(f"用户询问: {msg.content[:100]}...")
            elif msg.role == MessageRole.ASSISTANT:
                key_points.append(f"回答要点: {msg.content[:100]}...")
        
        return "\n".join(key_points[-5:])


class SessionStore:
    """会话存储"""
    
    def __init__(self, storage_path: str = "data/sessions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Session] = {}
    
    def _get_file_path(self, session_id: str) -> Path:
        return self.storage_path / f"{session_id}.json"
    
    async def save(self, session: Session) -> bool:
        """保存会话"""
        try:
            file_path = self._get_file_path(session.id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            self._cache[session.id] = session
            return True
        except Exception as e:
            logger.error("Session save failed", session_id=session.id, error=str(e))
            return False
    
    async def load(self, session_id: str) -> Optional[Session]:
        """加载会话"""
        # 检查缓存
        if session_id in self._cache:
            return self._cache[session_id]
        
        try:
            file_path = self._get_file_path(session_id)
            if not file_path.exists():
                return None
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            session = Session.from_dict(data)
            self._cache[session_id] = session
            return session
        except Exception as e:
            logger.error("Session load failed", session_id=session_id, error=str(e))
            return None
    
    async def delete(self, session_id: str) -> bool:
        """删除会话"""
        try:
            file_path = self._get_file_path(session_id)
            if file_path.exists():
                file_path.unlink()
            self._cache.pop(session_id, None)
            return True
        except Exception as e:
            logger.error("Session delete failed", session_id=session_id, error=str(e))
            return False
    
    async def list_sessions(self, user_id: Optional[int] = None) -> List[str]:
        """列出会话"""
        sessions = []
        for file_path in self.storage_path.glob("*.json"):
            session_id = file_path.stem
            if user_id:
                session = await self.load(session_id)
                if session and session.user_id == user_id:
                    sessions.append(session_id)
            else:
                sessions.append(session_id)
        return sessions
    
    async def cleanup_expired(self, ttl_hours: int) -> int:
        """清理过期会话"""
        cutoff = datetime.now() - timedelta(hours=ttl_hours)
        deleted = 0
        
        for file_path in self.storage_path.glob("*.json"):
            try:
                session = await self.load(file_path.stem)
                if session and session.updated_at < cutoff:
                    await self.delete(session.id)
                    deleted += 1
            except Exception:
                pass
        
        return deleted


class SessionManager:
    """会话管理器"""
    
    def __init__(
        self,
        config: SessionConfig = None,
        summarize_fn: Optional[Callable] = None
    ):
        self.config = config or SessionConfig()
        self.token_counter = TokenCounter()
        self.compressor = ContextCompressor(summarize_fn)
        self.store = SessionStore() if self.config.persist_enabled else None
        self._sessions: Dict[str, Session] = {}
    
    def _generate_session_id(self, user_id: Optional[int] = None) -> str:
        """生成会话ID"""
        data = f"{user_id or ''}{time.time()}{id(self)}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    async def create_session(
        self,
        user_id: Optional[int] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Session:
        """创建会话"""
        session = Session(
            id=session_id or self._generate_session_id(user_id),
            user_id=user_id,
            system_prompt=system_prompt,
            metadata=metadata or {}
        )
        
        self._sessions[session.id] = session
        
        if self.store:
            await self.store.save(session)
        
        logger.info("Session created", session_id=session.id, user_id=user_id)
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        # 内存缓存
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # 持久化存储
        if self.store:
            session = await self.store.load(session_id)
            if session:
                self._sessions[session_id] = session
                return session
        
        return None
    
    async def add_user_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Message:
        """添加用户消息"""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        token_count = self.token_counter.count(content)
        msg = session.add_message(
            MessageRole.USER,
            content,
            metadata=metadata or {},
            token_count=token_count
        )
        
        if self.store:
            await self.store.save(session)
        
        return msg
    
    async def add_assistant_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Message:
        """添加助手消息"""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        token_count = self.token_counter.count(content)
        msg = session.add_message(
            MessageRole.ASSISTANT,
            content,
            metadata=metadata or {},
            token_count=token_count
        )
        
        if self.store:
            await self.store.save(session)
        
        return msg
    
    async def get_context(
        self,
        session_id: str,
        max_tokens: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """获取对话上下文（用于LLM调用）"""
        session = await self.get_session(session_id)
        if not session:
            return []
        
        max_tokens = max_tokens or self.config.max_context_tokens
        
        # 获取消息
        messages = session.messages.copy()
        
        # 检查是否需要压缩
        current_tokens = self.token_counter.count_messages(messages)
        
        if current_tokens > max_tokens and self.config.auto_summarize:
            messages, summary = await self.compressor.compress(
                messages,
                max_tokens,
                self.token_counter
            )
            
            if summary:
                session.summaries.append(summary)
                if self.store:
                    await self.store.save(session)
        
        # 转换为LLM格式
        context = []
        
        # 添加系统提示
        if session.system_prompt:
            context.append({
                "role": "system",
                "content": session.system_prompt
            })
        
        # 添加摘要
        for summary in session.summaries[-2:]:  # 最多保留2个摘要
            context.append({
                "role": "system",
                "content": f"[历史对话摘要]\n{summary.content}"
            })
        
        # 添加消息
        for msg in messages:
            context.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        return context
    
    async def get_context_window(
        self,
        session_id: str,
        window_size: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """获取滑动窗口上下文"""
        session = await self.get_session(session_id)
        if not session:
            return []
        
        window_size = window_size or self.config.sliding_window_size
        recent_messages = session.get_recent_messages(window_size)
        
        context = []
        if session.system_prompt:
            context.append({
                "role": "system",
                "content": session.system_prompt
            })
        
        for msg in recent_messages:
            context.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        return context
    
    async def clear_session(self, session_id: str) -> bool:
        """清空会话消息"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.messages.clear()
        session.summaries.clear()
        session.total_tokens = 0
        session.updated_at = datetime.now()
        
        if self.store:
            await self.store.save(session)
        
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        self._sessions.pop(session_id, None)
        
        if self.store:
            return await self.store.delete(session_id)
        
        return True
    
    async def list_user_sessions(self, user_id: int) -> List[Session]:
        """列出用户的所有会话"""
        sessions = []
        
        # 内存中的会话
        for session in self._sessions.values():
            if session.user_id == user_id:
                sessions.append(session)
        
        # 持久化的会话
        if self.store:
            session_ids = await self.store.list_sessions(user_id)
            for sid in session_ids:
                if sid not in self._sessions:
                    session = await self.store.load(sid)
                    if session:
                        sessions.append(session)
        
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
    
    async def export_session(self, session_id: str) -> Optional[Dict]:
        """导出会话"""
        session = await self.get_session(session_id)
        if session:
            return session.to_dict()
        return None
    
    async def import_session(self, data: Dict) -> Session:
        """导入会话"""
        session = Session.from_dict(data)
        self._sessions[session.id] = session
        
        if self.store:
            await self.store.save(session)
        
        return session
    
    def get_stats(self, session_id: str) -> Optional[Dict]:
        """获取会话统计"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        user_messages = sum(1 for m in session.messages if m.role == MessageRole.USER)
        assistant_messages = sum(1 for m in session.messages if m.role == MessageRole.ASSISTANT)
        
        return {
            "session_id": session.id,
            "total_messages": len(session.messages),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "total_tokens": session.total_tokens,
            "summaries_count": len(session.summaries),
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "duration_minutes": (session.updated_at - session.created_at).total_seconds() / 60
        }
