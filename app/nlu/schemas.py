"""NLU 输出模型。"""
from typing import Any

from pydantic import BaseModel


class NLUResult(BaseModel):
    """意图分类与槽位提取结果。"""

    intent: str
    slots: dict[str, Any]
    confidence: float
