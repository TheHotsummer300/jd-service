"""应用装配测试：healthz 与电商意图注册。"""

from httpx import ASGITransport, AsyncClient

from app.business.registry import list_specs
from app.main import app


async def test_health_endpoint():
    """GET /healthz 应返回 200 且 data == "ok"。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == "ok"


def test_ecommerce_intents_registered_on_startup():
    """import app.main 后应触发电商意图注册。"""
    assert "order_query" in list_specs()
    assert "postsale_return" in list_specs()
    assert "product_inquiry" in list_specs()
