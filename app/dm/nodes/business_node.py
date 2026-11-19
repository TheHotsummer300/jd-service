"""业务节点 — 调用业务线的意图处理器

通过 IntentRegistry 动态获取意图对应的 Handler 类，
平台代码不直接导入任何业务线 Handler。
"""
from loguru import logger

from app.business.base import BusinessResult
from app.nlu.registry import IntentRegistry
from app.dm.intent_controller import IntentController


async def business_node(state: dict) -> dict:
    """执行业务意图

    通过 IntentController.get_active_context() 构建含独立槽位的上下文，
    业务完成后清空槽位但保持意图 active，以便后续复用同一意图。

    Returns:
        包含 business_result 和可能 intents 更新的字典。
    """
    active_intent = state.get("active_intent", "")

    handler_cls = IntentRegistry.get_handler(active_intent)
    if handler_cls is None:
        logger.warning(f"未找到意图处理器: {active_intent}")
        return {"business_result": BusinessResult.error("该功能暂未开放")}

    # 通过 Controller 构建上下文（含该意图的独立槽位）
    ctx = IntentController.get_active_context(state)

    handler = handler_cls()
    result = await handler.handle(ctx)

    # 读出 action 用于日志（兼容 ask_slot / completed / error 三种形态）
    action = ""
    if isinstance(result.data, dict):
        action = result.data.get("action", "")

    logger.info(
        f"业务节点执行: intent={active_intent}, "
        f"action={action}, "
        f"success={result.success}"
    )

    # 业务完成时清空槽位，保持意图 active 以便后续复用
    # （不再标记为 completed，否则 to_snapshot 会过滤掉导致 NLU 上下文丢失）
    if result.success and isinstance(result.data, dict):
        if result.data.get("action") == "completed":
            intents = dict(state.get("intents", {}))
            if active_intent and active_intent in intents:
                intents[active_intent]["slots"] = {}
                logger.info(
                    f"业务节点完成: intent={active_intent}, 槽位已清空，意图保持 active"
                )
                return {
                    "intents": intents,
                    "active_intent": active_intent,
                    "business_result": result,
                }

    return {"business_result": result}
