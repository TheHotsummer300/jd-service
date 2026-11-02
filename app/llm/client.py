"""LLM 调用封装：构建 ChatOpenAI 与文本生成。"""
from langchain_openai import ChatOpenAI
from loguru import logger

from app.config import Settings
from app.core.exceptions import LLMError

# 占位 key，视为未配置
_PLACEHOLDER_API_KEY = "sk-your-api-key"


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """构建 ChatOpenAI 实例，支持自定义 temperature；key 缺失或为占位值时抛 LLMError。"""
    settings = Settings()
    if not settings.llm_api_key or settings.llm_api_key == _PLACEHOLDER_API_KEY:
        raise LLMError("LLM API key 未配置")

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature,
    )


def get_chat_model() -> ChatOpenAI:
    """构建 ChatOpenAI 实例（temperature=0，用于需要确定性输出的场景）。"""
    return get_llm(temperature=0)


async def generate_text(prompt: str) -> str:
    """调用模型生成文本，失败时记录日志并统一转 LLMError。"""
    try:
        model = get_chat_model()
        result = await model.ainvoke(prompt)
        return result.content
    except LLMError:
        raise
    except Exception as exc:
        logger.error("LLM 调用失败: {}", exc)
        raise LLMError("LLM 调用失败") from exc
