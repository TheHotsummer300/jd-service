"""端到端集成验证：真实图 + 假 LLM 跑通整条链路。"""
import app.business.ecommerce  # noqa: F401  # 触发意图注册

from app.llm.schemas import IntentDecision


class _FakeModel:
    """假 LLM：结构化输出固定返回 order_query 意图。"""

    def with_structured_output(self, schema):
        class _Structured:
            async def ainvoke(self, prompt):
                return IntentDecision(intent="order_query", slots={"order_id": "A1"})

        return _Structured()


async def test_full_chat_flow(client, monkeypatch):
    """建会话 → 发消息 → 占位回显 → 取消息，整条链路无异常、数据正确。"""
    monkeypatch.setattr("app.dm.nodes.get_chat_model", lambda: _FakeModel())

    # 创建会话
    resp = await client.post("/api/v1/sessions", json={"user_id": "1001"})
    assert resp.status_code == 201
    session_id = resp.json()["data"]["id"]

    # 会话列表含该会话
    resp = await client.get("/api/v1/users/1001/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["data"]
    assert any(s["id"] == session_id for s in sessions)

    # 发消息，返回占位回显
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/chat", json={"content": "查订单"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["intent"] == "order_query"
    assert "order_query" in body["data"]["reply"]

    # 消息列表：user + assistant 两条，顺序正确
    resp = await client.get(f"/api/v1/sessions/{session_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()["data"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert "order_query" in messages[1]["content"]

    # 再次取会话列表无异常
    resp = await client.get("/api/v1/users/1001/sessions")
    assert resp.status_code == 200
