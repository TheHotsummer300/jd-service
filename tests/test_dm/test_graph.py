"""DM 层 LangGraph 状态机测试：粘性意图多轮填充与平台意图兜底。"""

import app.business.ecommerce  # noqa: F401  # 触发电商意图注册
from app.dm.graph import build_graph
from app.dm.state import dump_state, load_state
from app.nlg.llm_generator import LLMGenerator
from app.nlu.classifier import IntentClassifier
from app.nlu.schemas import NLUResult


def _initial_state() -> dict:
    """构造一轮对话的初始 DialogState。"""
    return {
        "session_id": "s1",
        "user_id": "1001",
        "user_message": "你好",
        "history": [],
        "intents": {},
        "active_intent": None,
        "slots": {},
        "nlu_result": None,
        "business_result": None,
        "response": None,
    }


def _patch_classifier(monkeypatch, nlu_result: NLUResult) -> None:
    """将 IntentClassifier.classify 替换为固定返回 nlu_result 的实现。"""

    async def fake_classify(
        self,
        text,
        active_intent,
        filled_slots,
        history,
        candidates,
        intent_descriptions=None,
    ):
        return nlu_result

    monkeypatch.setattr(IntentClassifier, "classify", fake_classify)
    # 隔离真实 LLM key 依赖，避免节点构造 ChatOpenAI 时读 .env
    monkeypatch.setattr("app.dm.nodes.get_chat_model", lambda: object())


async def test_unknown_intent_routes_to_fallback(monkeypatch):
    """平台意图 unknown 应路由到 fallback，由 LLM 生成回复且不触发业务。"""
    _patch_classifier(
        monkeypatch, NLUResult(intent="unknown", slots={}, confidence=0.0)
    )

    async def fake_generate(self, prompt):
        return "fallback reply"

    monkeypatch.setattr(LLMGenerator, "generate", fake_generate)

    result = await build_graph().ainvoke(_initial_state())

    assert result["response"] == "fallback reply"
    assert result["business_result"] is None


async def test_slot_filling_preserves_active_intent_across_turns(monkeypatch):
    """粘性意图：首轮识别售后意图并追问订单号，次轮补全订单号后走业务。"""
    # 第一轮：识别 postsale_return，触发订单号追问
    _patch_classifier(
        monkeypatch, NLUResult(intent="postsale_return", slots={}, confidence=1.0)
    )
    first = await build_graph().ainvoke(_initial_state())

    assert "order_id" in first["response"]
    assert first["active_intent"] == "postsale_return"

    # 持久化跨轮状态，再以新消息进入第二轮
    persisted = dump_state(first)
    second_state = load_state(
        persisted,
        session_id="s1",
        user_id="1001",
        user_message="A100",
        history=[],
    )

    # 第二轮：unknown（用户直接给订单号），应保留粘性意图并补全槽位
    _patch_classifier(
        monkeypatch, NLUResult(intent="unknown", slots={}, confidence=0.0)
    )
    second = await build_graph().ainvoke(second_state)

    assert second["active_intent"] == "postsale_return"
    assert second["slots"]["order_id"] == "A100"


async def test_nlu_node_passes_intent_descriptions(monkeypatch):
    """nlu_node 应将意图中文描述传给分类器，避免仅凭英文名误判。"""
    captured = {}

    async def fake_classify(
        self,
        text,
        active_intent,
        filled_slots,
        history,
        candidates,
        intent_descriptions=None,
    ):
        captured["descriptions"] = intent_descriptions
        return NLUResult(
            intent="product_inquiry",
            slots={"product_name": "iPhone16"},
            confidence=1.0,
        )

    monkeypatch.setattr(IntentClassifier, "classify", fake_classify)
    monkeypatch.setattr("app.dm.nodes.get_chat_model", lambda: object())

    await build_graph().ainvoke(_initial_state())

    assert captured["descriptions"]["product_inquiry"] == "商品咨询"
    assert captured["descriptions"]["order_query"] == "订单查询"
    assert captured["descriptions"]["unknown"] == "无法识别意图"
