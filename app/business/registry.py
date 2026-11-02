"""业务意图注册中心。

平台不硬编码任何业务线意图：意图名称 / 描述 / 槽位 / 追问文案均由业务层
通过 IntentSpec 定义并注册，NLU 与 DM 从注册中心动态读取。
"""
from typing import Any, Callable

from pydantic import BaseModel

# handler 约定签名：async def handle(intent, slots, user_message=None) -> dict
# user_message 为可选第三参，供 product_inquiry 等意图取回用户原始提问做 NLG。
Handler = Callable[..., Any]


class SlotSpec(BaseModel):
    """槽位规格。"""

    name: str
    required: bool
    description: str = ""
    enum: list[str] | None = None
    prompt: str = ""


class IntentSpec(BaseModel):
    """意图规格：名称、描述与槽位列表。"""

    name: str
    description: str
    slots: list[SlotSpec]


# 模块级单例注册表
_specs: dict[str, IntentSpec] = {}
_handlers: dict[str, Handler] = {}


def register(intent_spec: IntentSpec, handler: Handler) -> None:
    """注册一个意图规格及其处理器。"""
    _specs[intent_spec.name] = intent_spec
    _handlers[intent_spec.name] = handler


def get_handler(intent: str) -> Handler | None:
    """按意图名取处理器，未注册返回 None。"""
    return _handlers.get(intent)


def get_spec(intent: str) -> IntentSpec | None:
    """按意图名取规格，未注册返回 None。"""
    return _specs.get(intent)


def list_specs() -> dict[str, IntentSpec]:
    """返回全部已注册意图规格。"""
    return dict(_specs)


def required_slots(intent: str) -> list[str]:
    """返回意图的必填槽位名列表，未注册返回空列表。"""
    spec = _specs.get(intent)
    if spec is None:
        return []
    return [slot.name for slot in spec.slots if slot.required]
