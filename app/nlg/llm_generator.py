"""LLM 文本生成器：用于闲聊 / unknown / fallback。"""
from app.llm.client import generate_text


class LLMGenerator:
    """委托 generate_text 生成回复。"""

    async def generate(self, prompt: str) -> str:
        """生成回复文本，失败由上层按 500 契约处理。"""
        return await generate_text(prompt)
