"""会话层 CRUD 服务"""
import uuid

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.session.models import Session, Message


class SessionService:
    """会话管理服务"""

    @staticmethod
    async def create_session(db: AsyncSession, user_id: str) -> Session:
        """创建新会话"""
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            status="active",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        logger.info(f"创建会话: {session.id}, 用户: {user_id}")
        return session

    @staticmethod
    async def list_sessions(
        db: AsyncSession, user_id: str, limit: int = 10
    ) -> list[Session]:
        """获取用户最近会话列表，按更新时间倒序"""
        result = await db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_session(
        db: AsyncSession, session_id: str
    ) -> Session | None:
        """获取单个会话"""
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_session_title(
        db: AsyncSession, session_id: str, title: str
    ) -> None:
        """更新会话标题"""
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(title=title)
        )
        await db.commit()

    @staticmethod
    async def save_intents_snapshot(
        db: AsyncSession, session_id: str, intents: dict
    ) -> None:
        """保存意图容器快照到 Session.intents_json"""
        from app.dm.intent_controller import IntentController
        snapshot = IntentController.to_snapshot(intents)
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(intents_json=snapshot)
        )
        await db.commit()

    @staticmethod
    async def load_intents_snapshot(
        db: AsyncSession, session_id: str
    ) -> dict | None:
        """从 Session.intents_json 加载意图容器快照"""
        from app.dm.intent_controller import IntentController
        session = await SessionService.get_session(db, session_id)
        if session and session.intents_json:
            return IntentController.from_snapshot(session.intents_json)
        return None


class MessageService:
    """消息管理服务"""

    @staticmethod
    async def add_message(
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        slots: dict | None = None,
        business_data: dict | None = None,
    ) -> Message:
        """添加消息"""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            slots_json=slots,
            business_data_json=business_data,
        )
        db.add(message)
        # 同时更新会话的 updated_at
        await db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(updated_at=func.now())
        )
        await db.commit()
        await db.refresh(message)
        logger.info(f"添加消息: session={session_id}, role={role}")
        return message

    @staticmethod
    async def list_messages(
        db: AsyncSession, session_id: str
    ) -> list[Message]:
        """获取会话消息列表，按时间正序"""
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
