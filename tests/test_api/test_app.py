"""应用装配测试：healthz 与电商意图注册。"""

from httpx import ASGITransport, AsyncClient

from app.business.registry import list_specs
from app.core.exceptions import AppError
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


async def test_app_error_returns_500_envelope():
    """未单独注册子类的 AppError 应走兜底 handler，返回统一 500 信封。"""

    @app.get("/_raise_app_error")
    async def _raise() -> None:
        raise AppError("boom")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/_raise_app_error")
    finally:
        app.router.routes.pop()  # 清理临时路由，避免污染其他测试

    assert resp.status_code == 500
    assert resp.json() == {
        "success": False,
        "data": None,
        "error": "服务内部错误",
        "meta": None,
    }
