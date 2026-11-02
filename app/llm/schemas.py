"""LLM 结构化输出 Schema。"""
from typing import Any

from pydantic import BaseModel


class IntentDecision(BaseModel):
    """NLU 意图决策结构，供 ChatOpenAI.with_structured_output 使用。"""

    intent: str
    slots: dict[str, Any]
