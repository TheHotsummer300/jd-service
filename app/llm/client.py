"""LLM 客户端封装 — ChatOpenAI 单例工厂"""
from langchain_openai import ChatOpenAI

from app.config import settings

_llm_instance: ChatOpenAI | None = None


def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    """获取 ChatOpenAI 实例（单例模式）

    首次调用时根据配置创建实例，后续调用返回同一实例。
    如需不同 temperature，请先调用 reset_llm() 或直接传入 temperature 参数。

    Args:
        temperature: LLM 温度参数，控制回复的随机性（0-2）

    Returns:
        ChatOpenAI: 全局共享的 LLM 客户端实例
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=temperature,
        )
    return _llm_instance


def reset_llm() -> None:
    """重置 LLM 单例（主要用于测试）"""
    global _llm_instance
    _llm_instance = None
