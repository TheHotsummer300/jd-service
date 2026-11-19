"""会话与消息 API 端点

REST + SSE：创建/查询会话 + 发送消息（SSE 流式返回 AI 回复）。
"""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.core.database import get_db
from app.core.response import success_response
from app.session.service import SessionService, MessageService
from app.dm.graph import build_dialog_graph
from app.dm.intent_controller import IntentController

router = APIRouter(prefix="/sessions", tags=["会话管理"])

# ── 模块级常量和单例 ──────────────────────────────────
_dialog_graph = build_dialog_graph()  # 编译一次，所有请求复用
_SSE_CHUNK_SIZE = 5
_SSE_CHUNK_DELAY = 0.02  # 秒


@router.post("")
async def create_session(
    user_id: str = Query(..., description="用户 ID"),
    db: AsyncSession = Depends(get_db),
):
    """创建新会话"""
    session = await SessionService.create_session(db, user_id)
    return success_response(
        data={
            "id": session.id,
            "user_id": session.user_id,
            "title": session.title,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
    )


@router.get("")
async def list_sessions(
    user_id: str = Query(..., description="用户 ID"),
    db: AsyncSession = Depends(get_db),
):
    """获取会话列表（最多 10 个，按更新时间倒序）"""
    sessions = await SessionService.list_sessions(db, user_id, limit=10)
    data = [
        {
            "id": s.id,
            "user_id": s.user_id,
            "title": s.title,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]
    return success_response(data=data)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情及消息列表"""
    session = await SessionService.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = await MessageService.list_messages(db, session_id)

    return success_response(
        data={
            "session": {
                "id": session.id,
                "user_id": session.user_id,
                "title": session.title,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            },
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "intent": m.intent,
                    "slots_json": m.slots_json,
                    "business_data": m.business_data_json,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        }
    )


@router.post("/{session_id}/messages")
async def send_message(
    session_id: str,
    content: str = Query(..., description="消息内容"),
    db: AsyncSession = Depends(get_db),
):
    """发送消息，SSE 流式返回 AI 回复

    SSE 事件类型：
    - ``message``: 回复文本片段（逐块发送，前端逐字展示）
    - ``done``: 回复完成，结束流
    """
    # ── 1. 验证会话存在 ──────────────────────────────────
    session = await SessionService.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    # ── 2. 保存用户消息 ──────────────────────────────────
    await MessageService.add_message(db, session_id, "user", content)

    # ── 3. 自动设置会话标题（首次发言）───────────────────
    if not session.title:
        title = content[:50] + ("..." if len(content) > 50 else "")
        await SessionService.update_session_title(db, session_id, title)

    # ── 4. 加载历史消息构造 messages 上下文 ──────────────
    history_messages = await MessageService.list_messages(db, session_id)
    messages_context = [
        {"role": m.role, "content": m.content}
        for m in history_messages
    ]

    # ── 5. 从 DB 恢复意图状态 ────────────────────────────
    saved_intents = await SessionService.load_intents_snapshot(db, session_id)
    initial_intents = saved_intents if saved_intents else {}

    # ── 6. 构造初始状态 ──────────────────────────────────
    initial_state = {
        "session_id": session_id,
        "user_id": session.user_id,
        "user_input": content,
        "messages": messages_context,
        "all_intents": IntentController.build_all_intents(),
        "intents": initial_intents,
        "active_intent": IntentController.find_active(initial_intents),
        "business_result": None,
        "final_response": "",
        "should_fallback": False,
    }

    # ── 7. 执行对话图 ──────────────────────────────────
    try:
        final_state = await _dialog_graph.ainvoke(initial_state)
        reply = final_state.get("final_response", "抱歉，我不知道该如何回答。")
        active_intent = final_state.get("active_intent", "")
        active_slots = IntentController.get_active_slots(final_state)
    except Exception:
        logger.exception("对话图执行失败")
        reply = "抱歉，服务暂时不可用，请稍后再试。"
        active_intent = ""
        active_slots = {}
        final_state = {}  # 防止后续用 final_state 时 UnboundLocalError

    # ── 8. 持久化意图状态 ────────────────────────────────
    try:
        await SessionService.save_intents_snapshot(
            db, session_id, final_state.get("intents", {})
        )
    except Exception:
        logger.exception("意图状态持久化失败，跳过")

    # ── 9. 保存 AI 回复 ──────────────────────────────────
    # 只存 BusinessResult.data（内层的 {action, message, options, ...}）
    # 与 SSE done 事件中前端解包后的结构一致
    business_result = final_state.get("business_result")
    business_data_dict: dict | None = None
    if (
        business_result is not None
        and hasattr(business_result, "data")
        and isinstance(business_result.data, dict)
    ):
        business_data_dict = business_result.data
    await MessageService.add_message(
        db,
        session_id,
        "assistant",
        reply,
        intent=active_intent if active_intent else None,
        slots=active_slots if active_slots else None,
        business_data=business_data_dict,
    )

    # ── 10. SSE 流式返回 ─────────────────────────────────
    async def event_generator():
        """逐块发送回复文本，模拟 LLM 流式输出效果

        SSE 事件：
        - message: 回复文本片段
        - done: 回复完成，data 为 JSON，包含 intent/slots/business_data/message 全量文本
        """
        # 先发送文本片段
        for i in range(0, len(reply), _SSE_CHUNK_SIZE):
            chunk = reply[i:i + _SSE_CHUNK_SIZE]
            yield {"event": "message", "data": chunk}
            await asyncio.sleep(_SSE_CHUNK_DELAY)

        # 构造 done 事件的元数据
        # business_data 传内层 data（{action, message, options, ...}），与 DB 存储一致
        business_result = final_state.get("business_result")
        sse_business_data: dict | None = None
        if (
            business_result is not None
            and hasattr(business_result, "data")
            and isinstance(business_result.data, dict)
        ):
            sse_business_data = business_result.data
        done_meta = {
            "intent": active_intent if active_intent else None,
            "slots_json": active_slots if active_slots else None,
            "business_data": sse_business_data,
            "message": reply,
        }
        yield {"event": "done", "data": json.dumps(done_meta, ensure_ascii=False)}

    return EventSourceResponse(event_generator())
