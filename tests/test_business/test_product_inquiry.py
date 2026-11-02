"""product_inquiry 意图处理器测试：GraphRAG 检索编排与 NLG 生成。"""
import app.business.ecommerce  # noqa: F401  # 触发电商意图注册

from app.business.ecommerce import actions
from app.business.ecommerce.product_retrieval import SearchResult


class _FakeGraphRAG:
    """假 GraphRAG：记录 query 并返回预置结果。"""

    def __init__(self, results: list[SearchResult]):
        self._results = results
        self.query: str | None = None

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        self.query = query
        return self._results


async def test_product_inquiry_orchestrates_search_and_nlg(monkeypatch):
    # Arrange
    results = [
        SearchResult(
            text="商品名称: iPhone 12，价格: 6299.0",
            metadata={"source": "商品信息", "raw_data": {}},
            score=0.9,
        )
    ]
    fake = _FakeGraphRAG(results)

    async def fake_get_graphrag():
        return fake

    async def fake_generate_reply(query, results):
        return "您好！iPhone 12 支持双卡双待～"

    monkeypatch.setattr(actions, "_get_graphrag", fake_get_graphrag)
    monkeypatch.setattr(actions, "_generate_reply", fake_generate_reply)

    # Act
    result = await actions.handle(
        "product_inquiry", {"product_name": "iPhone 12"}, "iPhone 12 支持双卡双待吗"
    )

    # Assert
    assert fake.query == "iPhone 12 支持双卡双待吗"
    assert result["reply"] == "您好！iPhone 12 支持双卡双待～"
    assert result["results"][0]["text"] == "商品名称: iPhone 12，价格: 6299.0"
    assert result["results"][0]["source"] == "商品信息"


async def test_product_inquiry_falls_back_to_product_name(monkeypatch):
    # Arrange
    fake = _FakeGraphRAG([])

    async def fake_get_graphrag():
        return fake

    async def fake_generate_reply(query, results):
        return "回复"

    monkeypatch.setattr(actions, "_get_graphrag", fake_get_graphrag)
    monkeypatch.setattr(actions, "_generate_reply", fake_generate_reply)

    # Act：无 user_message 时用 product_name 作为检索 query
    result = await actions.handle("product_inquiry", {"product_name": "iPhone 12"}, None)

    # Assert
    assert fake.query == "iPhone 12"
    assert result["reply"] == "回复"


async def test_product_inquiry_graphrag_error_returns_busy_reply(monkeypatch):
    # Arrange
    async def broken_get_graphrag():
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(actions, "_get_graphrag", broken_get_graphrag)

    # Act
    result = await actions.handle(
        "product_inquiry", {"product_name": "iPhone 12"}, "iPhone 12 双卡双待"
    )

    # Assert：检索故障不应误导为“查无此商品”，而是返回“暂时繁忙”提示
    assert "繁忙" in result["reply"]
    assert result["results"] == []


async def test_product_inquiry_empty_query_prompts_for_name():
    # Act：无 user_message 且无 product_name
    result = await actions.handle("product_inquiry", {}, None)

    # Assert
    assert "哪款商品" in result["reply"]
    assert result["results"] == []


async def test_other_intents_remain_placeholder():
    # Act：order_query 仍走占位回显（第三参默认 None）
    result = await actions.handle("order_query", {"order_id": "A1"})

    # Assert
    assert result == {"intent": "order_query", "slots": {"order_id": "A1"}}


def test_format_results_serializes():
    # Arrange
    results = [
        SearchResult(text="t", metadata={"source": "商品信息", "raw_data": {}}, score=1.0)
    ]

    # Act
    formatted = actions._format_results(results)

    # Assert
    assert formatted == [{"text": "t", "score": 1.0, "source": "商品信息"}]


async def test_generate_reply_no_results():
    # Act
    reply = await actions._generate_reply("iPhone 12", [])

    # Assert
    assert "没有查询到" in reply


async def test_generate_reply_calls_llm(monkeypatch):
    # Arrange
    class _Reply:
        content = "您好！根据商品信息，iPhone 12 支持双卡双待。"

    class _FakeLLM:
        async def ainvoke(self, prompt):
            return _Reply()

    monkeypatch.setattr(actions, "get_chat_model", lambda: _FakeLLM())

    results = [
        SearchResult(
            text="iPhone 12 支持双卡双待",
            metadata={"source": "商品信息", "raw_data": {}},
            score=0.9,
        )
    ]

    # Act
    reply = await actions._generate_reply("iPhone 12 支持双卡双待吗", results)

    # Assert
    assert "双卡双待" in reply


async def test_generate_reply_falls_back_to_concatenation(monkeypatch):
    # Arrange：LLM 调用失败，降级为检索文本拼接
    def broken_llm():
        raise RuntimeError("llm down")

    monkeypatch.setattr(actions, "get_chat_model", broken_llm)

    results = [
        SearchResult(
            text="商品名称: iPhone 12，价格: 6299.0",
            metadata={"source": "商品信息", "raw_data": {}},
            score=1.0,
        )
    ]

    # Act
    reply = await actions._generate_reply("iPhone 12", results)

    # Assert
    assert "iPhone 12" in reply
