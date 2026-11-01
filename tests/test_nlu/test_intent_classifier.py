"""NLU 意图分类器测试。"""
import pytest

from app.core.exceptions import LLMError
from app.llm.schemas import IntentDecision
from app.nlu.classifier import IntentClassifier


class _FakeModel:
    """不含真实 LLM 的占位模型，供 monkeypatch 控制行为。"""

    def with_structured_output(self, schema):
        raise NotImplementedError


class _FakeStructured:
    """模拟 with_structured_output 返回的可调用对象。"""

    def __init__(self, result):
        self._result = result

    async def ainvoke(self, prompt):
        return self._result


async def test_unknown_intent_falls_back(monkeypatch):
    """分类结果不在候选集内时兜底 unknown（Review Focus #2）。"""
    model = _FakeModel()
    classifier = IntentClassifier(model)

    decision = IntentDecision(intent="不存在的意图", slots={})
    monkeypatch.setattr(
        model, "with_structured_output", lambda schema: _FakeStructured(decision)
    )

    result = await classifier.classify(
        "帮我查订单",
        active_intent=None,
        filled_slots={},
        history=[],
        candidates=["unknown", "transfer_human", "order_query"],
    )

    assert result.intent == "unknown"
    assert result.slots == {}
    assert result.confidence == 0.0


async def test_classify_passes_through_llm_error(monkeypatch):
    """结构化输出调用抛 LLMError 时透传，不吞成 unknown。"""

    class _RaisingStructured:
        async def ainvoke(self, prompt):
            raise LLMError("timeout")

    model = _FakeModel()
    classifier = IntentClassifier(model)
    monkeypatch.setattr(
        model, "with_structured_output", lambda schema: _RaisingStructured()
    )

    with pytest.raises(LLMError):
        await classifier.classify(
            "帮我查订单",
            active_intent=None,
            filled_slots={},
            history=[],
            candidates=["unknown", "transfer_human", "order_query"],
        )
