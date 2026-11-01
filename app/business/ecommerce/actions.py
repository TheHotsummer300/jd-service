"""电商业务线占位处理器：回显 intent 与 slots。"""
from typing import Any


async def handle(intent: str, slots: dict[str, Any]) -> dict[str, Any]:
    """占位实现：返回可模板化的回显 dict。"""
    return {"intent": intent, "slots": slots}
