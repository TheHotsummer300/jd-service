"""业务层注册中心测试。"""
from app.business.registry import (
    IntentSpec,
    SlotSpec,
    get_handler,
    get_spec,
    list_specs,
    register,
    required_slots,
)


def test_register_and_query():
    """注册意图后可按名查询 spec / handler，required_slots 返回必填槽位。"""
    spec = IntentSpec(name="fake", description="假意图", slots=[SlotSpec(name="x", required=True)])

    async def fake_handler(intent, slots):
        return {"intent": intent, "slots": slots}

    register(spec, fake_handler)

    assert get_spec("fake") == spec
    assert get_handler("fake") is fake_handler
    assert "fake" in list_specs()
    assert required_slots("fake") == ["x"]
    assert required_slots("nonexistent") == []
