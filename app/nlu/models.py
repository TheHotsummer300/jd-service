"""NLU 层核心数据模型"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SlotDef(BaseModel):
    """槽位定义

    描述意图所需的每个槽位，用于 LLM 理解和追问提示。
    """

    name: str = Field(..., description="槽位名称")
    description: str = Field(..., description="槽位描述，用于 LLM 理解")
    ask_prompt: str = Field(
        default="",
        description="追问提示语，用于向用户追问该槽位值",
    )


class IntentDefinition(BaseModel):
    """意图定义

    描述一个意图的名称、含义以及所需的槽位。
    """

    name: str = Field(..., description="意图唯一名称")
    description: str = Field(..., description="意图描述，用于 LLM 分类")
    required_slots: list[SlotDef] = Field(default_factory=list)
    optional_slots: list[SlotDef] = Field(default_factory=list)
    handler: Any = Field(
        default=None,
        description="对应的 IntentHandler 子类，平台代码不直接引用",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class NLUResult(BaseModel):
    """NLU 层输出 — 增量式意图变化

    只描述"本轮发生了什么变化"，不输出整个会话的意图状态。
    """

    action: str = Field(
        default="continue",
        description="变化类型：continue | switch | new | cancel | complete",
    )
    target_intent: str = Field(
        default="",
        description="目标意图名",
    )
    confidence: float = Field(default=0.0, description="置信度 0-1")
    slots_update: dict[str, object] = Field(
        default_factory=dict,
        description="本次新增/更新的槽位（增量，仅对目标意图有效）",
    )
