"""POST /chat 薄编排端点（Spec §6.6.1）。"""

import uuid

from fastapi import APIRouter
from loguru import logger

from app.api.schemas import ApiResponse
from app.api.v1.schemas import ChatReply, MessageCreate
from app.core.database import get_session_factory
from app.core.exceptions import LLMError, NotFoundError
from app.dm.graph import build_graph
from app.dm.state import dump_state, load_state
from app.session.schemas import MessageOut
from app.session.service import SessionService, session_title_from_content

router = APIRouter()


@router.post("/sessions/{session_id}/chat", response_model=ApiResponse[ChatReply])
async def chat(session_id: uuid.UUID, body: MessageCreate) -> ApiResponse[ChatReply]:
    """运行对话图并返回回复，user/assistant 消息与上下文一并落库。"""
    factory = get_session_factory()

    # 1. 读会话、历史、持久化状态（结束后释放 DB 会话）
    async with factory() as session:
        service = SessionService(session)
        chat_session = await service.get_session(session_id)
        if chat_session is None:
            raise NotFoundError("会话不存在")
        history = await service.list_messages(session_id)
        persisted = await service.load_dialog_state(session_id)
        user_id = chat_session.user_id

    # 首条用户消息对应的会话标题（提前算好，供 3a/3b 复用）
    title = session_title_from_content(body.content)

    # 2. 运行对话图（LLM 调用期间不持有 DB 会话/事务）
    state = load_state(
        persisted,
        session_id=str(session_id),
        user_id=user_id,
        user_message=body.content,
        history=[MessageOut.model_validate(m).model_dump() for m in history],
    )
    try:
        result_state = await build_graph().ainvoke(state)
    except LLMError as exc:
        logger.error("对话图执行失败: {}", exc)
        # 3a. LLM 失败：user 消息仍落库，再抛给异常 handler 转 500
        async with factory() as session:
            service = SessionService(session)
            await service.add_message(session_id, "user", body.content)
            if not history:
                await service.update_title(session_id, title)
        raise

    reply = result_state["response"]
    intent = result_state["active_intent"]
    slots = result_state["slots"]

    # 3b. 落 user + assistant 消息，回写 dialog_state
    async with factory() as session:
        service = SessionService(session)
        await service.add_message(session_id, "user", body.content)
        await service.add_message(
            session_id, "assistant", reply, intent=intent, slots=slots
        )
        await service.save_dialog_state(session_id, dump_state(result_state))
        # 首条用户消息：用消息内容更新会话标题，方便客户在列表中识别历史对话
        if not history:
            await service.update_title(session_id, title)

    return ApiResponse(
        success=True,
        data=ChatReply(reply=reply, intent=intent, slots=slots, session_id=session_id),
        error=None,
        meta=None,
    )
