"""LLM 客户端封装测试。"""
import pytest
from langchain_openai import ChatOpenAI

from app.core.exceptions import LLMError
from app.llm.client import generate_text, get_chat_model


async def test_generate_text_raises_llm_error_on_failure(monkeypatch):
    """LLM 调用抛异常时，generate_text 统一转为 LLMError（Review Focus #1）。"""

    async def fake_ainvoke(self, prompt):
        raise Exception("timeout")

    monkeypatch.setattr(ChatOpenAI, "ainvoke", fake_ainvoke)

    with pytest.raises(LLMError):
        await generate_text("hello")


def test_get_chat_model_raises_on_missing_key(monkeypatch):
    """llm_api_key 为空时，get_chat_model 抛 LLMError。"""
    monkeypatch.setenv("LLM_API_KEY", "")

    with pytest.raises(LLMError):
        get_chat_model()
