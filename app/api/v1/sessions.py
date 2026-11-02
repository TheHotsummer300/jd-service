"""会话与消息查询端点。"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.schemas import ApiResponse
from app.api.v1.schemas import SessionCreate
from app.core.exceptions import NotFoundError
from app.session.schemas import MessageOut, SessionOut
from app.session.service import SessionService

router = APIRouter()


@router.post("/sessions", response_model=ApiResponse[SessionOut], status_code=201)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db)
) -> ApiResponse[SessionOut]:
    """创建会话。"""
    service = SessionService(db)
    chat_session = await service.create_session(body.user_id)
    return ApiResponse(
        success=True,
        data=SessionOut.model_validate(chat_session),
        error=None,
        meta=None,
    )


@router.get("/users/{user_id}/sessions", response_model=ApiResponse[list[SessionOut]])
async def list_sessions(
    user_id: str, db: AsyncSession = Depends(get_db)
) -> ApiResponse[list[SessionOut]]:
    """返回用户会话列表（updated_at 倒序）。"""
    service = SessionService(db)
    sessions = await service.list_sessions(user_id)
    return ApiResponse(
        success=True,
        data=[SessionOut.model_validate(s) for s in sessions],
        error=None,
        meta=None,
    )


@router.get(
    "/sessions/{session_id}/messages", response_model=ApiResponse[list[MessageOut]]
)
async def list_messages(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ApiResponse[list[MessageOut]]:
    """返回会话消息列表（created_at 正序）；会话不存在则 404。"""
    service = SessionService(db)
    if await service.get_session(session_id) is None:
        raise NotFoundError("会话不存在")
    messages = await service.list_messages(session_id)
    return ApiResponse(
        success=True,
        data=[MessageOut.model_validate(m) for m in messages],
        error=None,
        meta=None,
    )
