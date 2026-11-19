"""会话层 Pydantic 输出模型。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionOut(BaseModel):
    """会话输出模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    """消息输出模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    intent: str | None
    slots: dict | None
    created_at: datetime
