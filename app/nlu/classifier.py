"""LLM 驱动的意图分类与槽位提取。"""
import json
from typing import Any

from langchain_openai import ChatOpenAI
from loguru import logger

from app.core.exceptions import LLMError
from app.llm.schemas import IntentDecision
from app.nlu.schemas import NLUResult

# 结构化输出失败时降级 JSON mode 的重试次数
_JSON_RETRY_COUNT = 2


class IntentClassifier:
    """基于 ChatOpenAI 的意图分类器。

    候选意图由调用方（DM）传入，本模块不 import 业务层、不硬编码任何电商意图。
    """

    def __init__(self, model: ChatOpenAI):
        self._model = model

    async def classify(
        self,
        text: str,
        active_intent: str | None,
        filled_slots: dict[str, Any],
        history: list[Any],
        candidates: list[str],
    ) -> NLUResult:
        """分类用户消息，返回意图与槽位。非候选意图或失败兜底 unknown。"""
        prompt = self._build_prompt(text, active_intent, filled_slots, history, candidates)

        decision = await self._call_structured(prompt)
        if decision is None:
            return NLUResult(intent="unknown", slots={}, confidence=0.0)

        if decision.intent not in candidates:
            return NLUResult(intent="unknown", slots={}, confidence=0.0)

        return NLUResult(intent=decision.intent, slots=decision.slots, confidence=1.0)

    def _build_prompt(
        self,
        text: str,
        active_intent: str | None,
        filled_slots: dict[str, Any],
        history: list[Any],
        candidates: list[str],
    ) -> str:
        """拼接分类 prompt：用户消息 + 当前意图 + 已填槽位 + 历史 + 候选意图。"""
        history_text = "\n".join(
            f"{msg.role}: {msg.content}" for msg in history if hasattr(msg, "role")
        )
        return (
            "你是电商智能客服的意图识别器。请判断用户消息的意图并抽取槽位。\n"
            f"候选意图：{', '.join(candidates)}\n"
            f"当前进行中的意图：{active_intent or '无'}\n"
            f"已填槽位：{json.dumps(filled_slots, ensure_ascii=False)}\n"
            f"最近历史：\n{history_text}\n"
            f"用户消息：{text}\n"
            "请输出 JSON：{\"intent\": \"<意图>\", \"slots\": {...}}"
        )

    async def _call_structured(self, prompt: str) -> IntentDecision | None:
        """优先走 with_structured_output；失败降级 JSON mode；仍失败返回 None。"""
        try:
            structured = self._model.with_structured_output(IntentDecision)
            return await structured.ainvoke(prompt)
        except LLMError:
            raise
        except Exception as exc:
            logger.warning("结构化输出不可用，降级 JSON mode: {}", exc)
            return await self._call_json_mode(prompt)

    async def _call_json_mode(self, prompt: str) -> IntentDecision | None:
        """JSON mode 降级：解析并校验，带重试，最终失败返回 None。"""
        for attempt in range(_JSON_RETRY_COUNT):
            try:
                result = await self._model.ainvoke(prompt)
                data = json.loads(result.content)
                return IntentDecision.model_validate(data)
            except LLMError:
                raise
            except Exception as exc:
                logger.warning("JSON mode 解析失败（第 {} 次）: {}", attempt + 1, exc)
        return None
