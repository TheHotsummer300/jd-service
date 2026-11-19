"""NLG 引擎 — 根据意图和业务结果路由到合适的生成策略"""

from app.nlg.llm_generator import LLMGenerator
from app.business.base import BusinessResult


class NLGEngine:
    """NLG 生成引擎

    职责：根据 intent 和 business_result 决定回复内容。

    - 有 BusinessResult 时直接使用其 message（由业务 Handler 已渲染好）
    - 兜底/unknown 时使用 LLM 生成
    - 转人工时返回固定文案

    注意：模板渲染由业务 Handler 负责，NLGEngine 不直接调用 TemplateEngine。
    槽位追问通过 BusinessResult.ask_slot() 的固定数据结构和前端沟通，
    无需 NLGEngine 额外处理。
    """

    def __init__(self):
        self._llm = LLMGenerator()

    async def generate(
        self,
        intent: str,
        business_result: BusinessResult | None = None,
        context: dict | None = None,
    ) -> str:
        """根据意图和业务结果生成回复

        Args:
            intent: 当前活跃意图名（如 "order_query"、"unknown" 等）
            business_result: 业务 Handler 的执行结果，非空时直接使用其 message
            context: 额外上下文，兜底场景时传入 {"user_input": "..."}

        Returns:
            最终要发送给用户的回复文本
        """
        context = context or {}

        # 有业务结果 → 渲染 message + options（如有）
        if business_result is not None:
            msg = business_result.message
            if isinstance(business_result.data, dict) and business_result.data.get("options"):
                lines = [msg, ""]
                for i, opt in enumerate(business_result.data["options"], 1):
                    label = opt.get("label", opt.get("value", "?"))
                    value = opt.get("value", "")
                    disabled = " [不可选]" if opt.get("disabled") else ""
                    lines.append(f"  {i}. {label}{disabled}  (回复: {value})")
                return "\n".join(lines)
            return msg

        # 转人工 → 固定文案
        if intent == "transfer_human":
            return "正在为您转接人工客服，请稍候..."

        # 兜底 / unknown → LLM 自由生成
        return await self._llm.generate(context.get("user_input", ""))