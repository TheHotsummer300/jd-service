"""NLG 层 — 混合策略：Jinja2 模板用于精确业务结果，LLM 用于闲聊/兜底"""

from app.nlg.template_engine import TemplateEngine
from app.nlg.llm_generator import LLMGenerator
from app.nlg.engine import NLGEngine

__all__ = ["TemplateEngine", "LLMGenerator", "NLGEngine"]
