"""NLG 模板引擎测试。"""
from app.nlg.template_engine import TemplateEngine


def test_render_slot_filling_with_enum():
    """带枚举的槽位追问模板渲染出槽位名、追问文案与选项。"""
    output = TemplateEngine().render(
        "slot_filling.j2",
        {
            "slot_name": "postsale_type",
            "prompt": "请选择售后类型",
            "enum": ["退款", "退货", "换货"],
        },
    )

    assert "postsale_type" in output
    assert "请选择售后类型" in output
    assert "退款" in output
    assert "退货" in output
    assert "换货" in output


def test_render_business_placeholder():
    """业务占位结果模板精确回显 intent 与 slots（不允许幻觉）。"""
    output = TemplateEngine().render(
        "business_placeholder.j2",
        {"intent": "order_query", "slots": {"order_id": "A1"}},
    )

    assert "order_query" in output
    assert "A1" in output
