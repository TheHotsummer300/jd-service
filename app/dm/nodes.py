"""DM 层节点函数：纯函数式，返回部分状态 dict 由 LangGraph 合并。"""

from typing import Any

from app.business.registry import (get_handler, get_spec, list_specs,
                                   required_slots)
from app.dm.state import DialogState, IntentContext
from app.llm.client import get_chat_model
from app.nlg.llm_generator import LLMGenerator
from app.nlg.template_engine import TemplateEngine
from app.nlu.classifier import IntentClassifier
from app.nlu.platform_intents import PLATFORM_INTENTS


def entry_node(state: DialogState) -> dict:
    """入口节点：当前无额外处理，透传状态。"""
    return {}


def merge_slots(filled: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """合并槽位：incoming 非空值覆盖 filled，空值不覆盖已填。"""
    merged = dict(filled)
    for key, value in incoming.items():
        if value not in (None, ""):
            merged[key] = value
    return merged


async def nlu_node(state: DialogState) -> dict:
    """意图分类 + 粘性意图槽位填充（Spec §6.6 精确语义）。"""
    user_message = state["user_message"]
    active_intent = state.get("active_intent")
    slots = dict(state.get("slots") or {})
    history = state.get("history", [])
    intents = dict(state.get("intents") or {})

    candidates = list(PLATFORM_INTENTS) + list(list_specs().keys())
    classifier = IntentClassifier(get_chat_model())
    nlu_result = await classifier.classify(
        text=user_message,
        active_intent=active_intent,
        filled_slots=slots,
        history=history,
        candidates=candidates,
    )

    slots = merge_slots(slots, nlu_result.slots)

    is_business_active = (
        active_intent is not None and active_intent not in PLATFORM_INTENTS
    )
    if is_business_active:
        required = required_slots(active_intent)
        missing = [name for name in required if not slots.get(name)]
        if missing:
            if nlu_result.intent == active_intent or nlu_result.intent == "unknown":
                # 保留粘性意图；本轮仍缺槽位时，用整条消息填第一个缺失槽位
                if not slots.get(missing[0]):
                    slots[missing[0]] = user_message
            else:
                # 切换新业务意图：写回旧意图槽位，读取新意图已有槽位
                intents[active_intent] = IntentContext(
                    intent=active_intent, slots=slots
                )
                active_intent = nlu_result.intent
                new_ctx = intents.get(active_intent)
                slots = dict(new_ctx.slots) if new_ctx else dict(nlu_result.slots)
                if active_intent not in intents:
                    intents[active_intent] = IntentContext(
                        intent=active_intent, slots=slots
                    )
    else:
        if nlu_result.intent in PLATFORM_INTENTS:
            active_intent = nlu_result.intent
            slots = {}
        else:
            active_intent = nlu_result.intent
            slots = dict(nlu_result.slots)
            intents[active_intent] = IntentContext(intent=active_intent, slots=slots)

    # 同步当前业务意图的槽位到 intents
    if active_intent is not None and active_intent not in PLATFORM_INTENTS:
        intents[active_intent] = IntentContext(intent=active_intent, slots=slots)

    return {
        "nlu_result": nlu_result,
        "intents": intents,
        "active_intent": active_intent,
        "slots": slots,
    }


def slot_filling_node(state: DialogState) -> dict:
    """对第一个缺失的必填槽位生成追问；已填满则保持 response 为 None。"""
    active_intent = state["active_intent"]
    if active_intent is None or active_intent in PLATFORM_INTENTS:
        return {}

    slots = state.get("slots") or {}
    missing = [name for name in required_slots(active_intent) if not slots.get(name)]
    if not missing:
        return {}

    spec = get_spec(active_intent)
    slot_spec = next(s for s in spec.slots if s.name == missing[0])
    response = TemplateEngine().render(
        "slot_filling.j2",
        {
            "slot_name": slot_spec.name,
            "prompt": slot_spec.prompt,
            "enum": slot_spec.enum,
        },
    )
    return {"response": response}


async def business_node(state: DialogState) -> dict:
    """调用业务处理器，写入 business_result。"""
    active_intent = state["active_intent"]
    slots = state.get("slots") or {}
    handler = get_handler(active_intent)
    if handler is None:
        return {}
    business_result = await handler(active_intent, slots, state.get("user_message"))
    return {"business_result": business_result}


def response_node(state: DialogState) -> dict:
    """business_result 非空时渲染业务结果模板；含 reply 时直接透传。"""
    business_result = state.get("business_result")
    if not business_result:
        return {}
    reply = business_result.get("reply")
    if reply:
        return {"response": reply}
    response = TemplateEngine().render("business_placeholder.j2", business_result)
    return {"response": response}


async def fallback_node(state: DialogState) -> dict:
    """平台意图/闲聊兜底：由 LLM 生成回复。"""
    response = await LLMGenerator().generate(state["user_message"])
    return {"response": response}
