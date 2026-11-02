"""会话层 CRUD 服务：会话 / 消息持久化与 dialog_state 读写。"""
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.session.models import ChatSession, Message


def session_title_from_content(content: str, max_length: int = 20) -> str:
    """从首条用户消息截取会话标题：合并空白、去除首尾，超长加省略号。"""
    text = " ".join((content or "").split())
    if not text:
        return "新会话"
    if len(text) <= max_length:
        return text
    return text[:max_length] + "…"


class SessionService:
    """会话与消息的持久化服务，方法均为异步。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_session(self, user_id: str) -> ChatSession:
        """创建会话并提交。"""
        chat_session = ChatSession(user_id=user_id, updated_at=datetime.now())
        self._session.add(chat_session)
        await self._session.commit()
        await self._session.refresh(chat_session)
        return chat_session

    async def list_sessions(self, user_id: str) -> list[ChatSession]:
        """按 updated_at 倒序返回用户会话列表。"""
        result = await self._session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_session(self, session_id: uuid.UUID) -> ChatSession | None:
        """按主键查询会话，不存在返回 None。"""
        return await self._session.get(ChatSession, session_id)

    async def list_messages(self, session_id: uuid.UUID) -> list[Message]:
        """按 created_at 正序返回会话消息列表。"""
        result = await self._session.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        intent: str | None = None,
        slots: dict | None = None,
    ) -> Message:
        """新增消息并刷新所属会话的 updated_at。"""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            slots=slots,
        )
        self._session.add(message)
        await self._session.flush()

        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is not None:
            # 显式更新，触发 onupdate 使会话排序前移（微秒精度，避免 SQLite 秒级精度下不变化）
            chat_session.updated_at = datetime.now()

        await self._session.commit()
        await self._session.refresh(message)
        return message

    async def load_dialog_state(self, session_id: uuid.UUID) -> dict | None:
        """读取会话的 dialog_state 原始 JSON，不存在返回 None。"""
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            return None
        return chat_session.dialog_state

    async def save_dialog_state(self, session_id: uuid.UUID, state: dict) -> None:
        """写回 dialog_state 并提交。"""
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            return
        chat_session.dialog_state = state
        await self._session.commit()

    async def update_title(self, session_id: uuid.UUID, title: str) -> None:
        """更新会话标题并提交。"""
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            return
        chat_session.title = title
        await self._session.commit()
