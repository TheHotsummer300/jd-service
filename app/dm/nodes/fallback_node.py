"""兜底节点 — 处理平台意图（unknown / transfer_human）"""
from loguru import logger


async def fallback_node(state: dict) -> dict:
    """处理 unknown 和 transfer_human 意图

    设置 should_fallback 标记，后续由 response_node 根据此标记
    和 active_intent 生成对应回复。

    Returns:
        包含 should_fallback=True 的更新字典。
    """
    active_intent = state.get("active_intent", "unknown")

    if active_intent == "transfer_human":
        logger.info("触发转人工")
    else:
        logger.info("触发 unknown 兜底")

    return {"should_fallback": True}
