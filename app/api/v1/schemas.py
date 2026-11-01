"""通道层 v1 请求/响应 Pydantic 模型。"""

import uuid
from typing import Annotated

from pydantic import BaseModel, StringConstraints

# 空白字符串（strip 后为空）不合法，由 FastAPI 转 422
_NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SessionCreate(BaseModel):
    """创建会话请求。"""

    user_id: _NonBlank


class MessageCreate(BaseModel):
    """发送消息请求。"""

    content: _NonBlank


class ChatReply(BaseModel):
    """聊天回复响应。"""

    reply: str
    intent: str
    slots: dict
    session_id: uuid.UUID
