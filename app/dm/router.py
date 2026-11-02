"""DM 层条件路由函数。"""

from typing import Literal

from app.dm.state import DialogState
from app.nlu.platform_intents import PLATFORM_INTENTS


def route_after_nlu(state: DialogState) -> Literal["fallback", "slot_filling"]:
    """平台意图走 fallback，业务意图走槽位填充。"""
    if state["active_intent"] in PLATFORM_INTENTS:
        return "fallback"
    return "slot_filling"


def route_after_slot_filling(state: DialogState) -> Literal["business", "end"]:
    """已生成追问则结束本轮；否则进入业务处理。"""
    if state.get("response") is not None:
        return "end"
    return "business"
