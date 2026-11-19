"""回复生成节点 — 调用 NLG 引擎生成最终回复"""
from app.nlg.engine import NLGEngine

_engine: NLGEngine | None = None


def get_engine() -> NLGEngine:
    """获取 NLGEngine 单例（懒加载）"""
    global _engine
    if _engine is None:
        _engine = NLGEngine()
    return _engine


def reset_engine() -> None:
    """重置引擎单例（用于测试）"""
    global _engine
    _engine = None


async def response_node(state: dict) -> dict:
    """生成最终回复

    NLGEngine.generate() 的输出策略：
    - 有 business_result → 直接使用 business_result.message
      （包括 ask_slot / completed / error 三种情况）
    - should_fallback + transfer_human → 硬编码"正在转接"文案
    - 其他兜底（unknown 等） → LLM 自由生成

    Returns:
        包含 final_response 的更新字典。
    """
    intent = state.get("active_intent", "unknown")
    business_result = state.get("business_result")
    should_fallback = state.get("should_fallback", False)
    user_input = state.get("user_input", "")

    engine = get_engine()

    # 构造传给 NLGEngine 的上下文
    context = {"user_input": user_input} if should_fallback else None

    response_text = await engine.generate(
        intent=intent,
        business_result=business_result,
        context=context,
    )
    return {"final_response": response_text}
