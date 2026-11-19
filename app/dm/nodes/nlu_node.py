"""NLU 节点 — 调用意图分类器进行意图识别和槽位提取"""
from loguru import logger

from app.nlu.classifier import IntentClassifier
from app.dm.intent_controller import IntentController

_classifier: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    """获取 IntentClassifier 单例（懒加载）"""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def reset_classifier() -> None:
    """重置分类器单例（用于测试）"""
    global _classifier
    _classifier = None


async def nlu_node(state: dict) -> dict:
    """NLU 节点：对用户输入进行意图变化识别和槽位提取

    将 all_intents、session_intents、active_intent 传递给分类器，
    然后委托 IntentController.decide() 处理意图生命周期。

    Returns:
        包含 intents、active_intent、should_fallback 的更新字典。
    """
    user_input = state.get("user_input", "")

    classifier = get_classifier()
    result = await classifier.classify(
        user_input=user_input,
        all_intents=state.get("all_intents", []),
        session_intents=state.get("intents", {}),
        active_intent=state.get("active_intent", ""),
        messages=state.get("messages", []),
    )

    # 委托 Controller 处理意图生命周期
    update = IntentController.decide(state, result)

    logger.info(
        f"NLU 节点输出: action={result.action}, "
        f"target={result.target_intent}, "
        f"confidence={result.confidence}, "
        f"slots_update={result.slots_update}, "
        f"active_intent={update.get('active_intent', '')}"
    )

    # 判断是否兜底
    update["should_fallback"] = (
        result.target_intent in ("unknown", "transfer_human")
    )

    return update
