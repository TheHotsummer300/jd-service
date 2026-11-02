"""通道层 REST 端点测试：统一信封、编排与失败契约。"""

import uuid

from app.core.exceptions import LLMError


async def test_create_session_requires_user_id(client):
    """空白 user_id 应 422（Review Focus #4），不落库、不触发 LLM。"""
    resp = await client.post("/api/v1/sessions", json={"user_id": "   "})
    assert resp.status_code == 422


async def test_chat_returns_assistant_reply_and_persists_two_messages(
    client, monkeypatch
):
    """发消息应返回 assistant 回复，且落 user + assistant 两条消息。"""
    # 创建会话
    resp = await client.post("/api/v1/sessions", json={"user_id": "1001"})
    assert resp.status_code == 201
    session_id = resp.json()["data"]["id"]

    # fake 图：固定返回占位回复
    class _FakeGraph:
        async def ainvoke(self, state):
            return {
                "response": "ok",
                "active_intent": "order_query",
                "slots": {},
                "intents": {},
            }

    monkeypatch.setattr("app.api.v1.chat.build_graph", lambda: _FakeGraph())

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/chat", json={"content": "查订单"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["reply"] == "ok"
    assert body["data"]["intent"] == "order_query"

    # 消息列表：user + assistant 两条，顺序正确
    resp = await client.get(f"/api/v1/sessions/{session_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()["data"]
    assert [m["role"] for m in messages] == ["user", "assistant"]


async def test_chat_unknown_session_404(client):
    """向不存在的会话发消息应 404（Review Focus #5），不静默新建会话。"""
    resp = await client.post(
        f"/api/v1/sessions/{uuid.uuid4()}/chat", json={"content": "你好"}
    )
    assert resp.status_code == 404


async def test_chat_llm_error_500_persists_user_message(client, monkeypatch):
    """LLM 失败应 500 信封 success=false，且 user 消息仍落库（Review Focus #1）。"""
    resp = await client.post("/api/v1/sessions", json={"user_id": "1001"})
    assert resp.status_code == 201
    session_id = resp.json()["data"]["id"]

    class _FailingGraph:
        async def ainvoke(self, state):
            raise LLMError("boom")

    monkeypatch.setattr("app.api.v1.chat.build_graph", lambda: _FailingGraph())

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/chat", json={"content": "查订单"}
    )
    assert resp.status_code == 500
    assert resp.json()["success"] is False

    # user 消息仍落库
    resp = await client.get(f"/api/v1/sessions/{session_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()["data"]
    assert [m["role"] for m in messages] == ["user"]
