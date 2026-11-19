"""LLM 回复生成器 — 用于闲聊/兜底场景"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from app.config import settings


class LLMGenerator:
    """LLM 生成器 — 用于闲聊/兜底场景

    使用 ChatOpenAI（通过 .env 配置的 model/api_key/base_url）生成自然语言回复。
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.7,
            )
        return self._llm

    async def generate(self, user_input: str) -> str:
        """生成自然语言回复

        Args:
            user_input: 用户输入的原始文本，用于 LLM 生成兜底回复

        Returns:
            生成的回复文本，失败时返回降级提示语
        """
        try:
            messages = [
                SystemMessage(
                    content="你是一个电商客服助手，请用中文回复用户。回复要友好、简洁、有帮助。"
                ),
                HumanMessage(content=user_input),
            ]
            response = await self.llm.ainvoke(messages)
            result = response.content.strip()
            logger.info("LLM 回复生成成功")
            return result
        except Exception as e:
            logger.error(f"LLM 回复生成失败: {e}")
            return "抱歉，我现在无法回答这个问题。请问还有其他可以帮助您的吗？"
