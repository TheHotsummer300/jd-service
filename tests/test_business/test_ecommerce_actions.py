"""电商业务线意图注册与占位处理器测试。"""
import app.business.ecommerce  # noqa: F401  # 触发意图注册

from app.business.registry import get_handler, list_specs, required_slots


async def test_ecommerce_registers_three_intents_and_placeholder():
    """三个电商意图已注册，槽位定义正确，占位处理器回显 intent + slots。"""
    specs = list_specs()

    assert "order_query" in specs
    assert "postsale_return" in specs
    assert "product_inquiry" in specs

    assert required_slots("postsale_return") == ["order_id"]
    assert required_slots("product_inquiry") == ["product_name"]
    assert required_slots("order_query") == []

    handler = get_handler("order_query")
    result = await handler("order_query", {"order_id": "A1"})
    assert result == {"intent": "order_query", "slots": {"order_id": "A1"}}
