"""会话层 ORM 模型"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Session(Base):
    """会话表"""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "closed", name="session_status"),
        nullable=False,
        default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    intents_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="会话意图状态快照: {intent_name: {status, slots, confidence, ...}}"
    )

    messages = relationship("Message", back_populates="session", lazy="selectin")


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", name="message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slots_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    business_data_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="业务结构化数据快照: ask_slot/options 等，前端据此恢复按钮"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    session = relationship("Session", back_populates="messages")
