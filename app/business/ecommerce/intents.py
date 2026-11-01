"""电商业务线意图规格定义（与 Spec §6.3 一致）。"""
from app.business.registry import IntentSpec, SlotSpec

ORDER_QUERY = IntentSpec(
    name="order_query",
    description="订单查询",
    slots=[
        SlotSpec(name="order_id", required=False, description="订单号", prompt="请提供订单号"),
    ],
)

POSTSALE_RETURN = IntentSpec(
    name="postsale_return",
    description="售后/退货",
    slots=[
        SlotSpec(name="order_id", required=True, description="订单号", prompt="请提供订单号"),
        SlotSpec(
            name="postsale_type",
            required=False,
            description="售后类型",
            enum=["退款", "退货", "换货"],
            prompt="请选择售后类型",
        ),
        SlotSpec(name="postsale_reason", required=False, description="售后原因", prompt="请描述售后原因"),
    ],
)

PRODUCT_INQUIRY = IntentSpec(
    name="product_inquiry",
    description="商品咨询",
    slots=[
        SlotSpec(name="product_name", required=True, description="商品名称", prompt="请提供商品名称"),
    ],
)

INTENT_SPECS = [ORDER_QUERY, POSTSALE_RETURN, PRODUCT_INQUIRY]
