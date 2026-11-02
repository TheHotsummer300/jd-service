"""DM 层状态定义与跨轮持久化转换。"""

from typing import Any, TypedDict

from pydantic import BaseModel

from app.nlu.schemas import NLUResult


class IntentContext(BaseModel):
    """单个意图上下文：意图名与已填槽位（Spec §6.6，无 status 字段）。"""

    intent: str
    slots: dict[str, Any]


class DialogState(TypedDict):
    """LangGraph 状态机的对话状态。"""

    session_id: str
    user_id: str
    user_message: str
    history: list[dict]
    intents: dict[str, IntentContext]
    active_intent: str | None
    slots: dict[str, Any]
    nlu_result: NLUResult | None
    business_result: dict[str, Any] | None
    response: str | None


def dump_state(state: DialogState) -> dict:
    """只返回跨轮持久化字段，供 session.save_dialog_state 使用。"""
    return {
        "intents": {name: ctx.model_dump() for name, ctx in state["intents"].items()},
        "active_intent": state["active_intent"],
        "slots": state["slots"],
    }


def load_state(
    persisted: dict | None,
    session_id: str,
    user_id: str,
    user_message: str,
    history: list[dict],
) -> DialogState:
    """从持久化字段恢复状态，无则新建空状态。"""
    if persisted:
        intents = {
            name: IntentContext(**data)
            for name, data in persisted.get("intents", {}).items()
        }
        return {
            "session_id": session_id,
            "user_id": user_id,
            "user_message": user_message,
            "history": history,
            "intents": intents,
            "active_intent": persisted.get("active_intent"),
            "slots": persisted.get("slots") or {},
            "nlu_result": None,
            "business_result": None,
            "response": None,
        }
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_message": user_message,
        "history": history,
        "intents": {},
        "active_intent": None,
        "slots": {},
        "nlu_result": None,
        "business_result": None,
        "response": None,
    }
