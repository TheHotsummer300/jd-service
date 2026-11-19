"""电商业务线意图定义"""
from app.nlu.models import IntentDefinition, SlotDef
from app.business.ecommerce.handlers.order_query import OrderQueryHandler
from app.business.ecommerce.handlers.postsale_return import PostsaleReturnHandler
from app.business.ecommerce.handlers.product_inquiry import ProductInquiryHandler

# 业务线统一导出的意图列表，变量名固定为 INTENTS
# 每个意图通过 handler 字段绑定对应的处理器类
INTENTS: list[IntentDefinition] = [
    IntentDefinition(
        name="order_query",
        description="用户查询自己的订单详情、订单状态或订单信息",
        required_slots=[
            SlotDef(
                name="order_id",
                description="订单号",
                ask_prompt="请提供您的订单号，我帮您查询详情",
            ),
        ],
        handler=OrderQueryHandler,
    ),
    IntentDefinition(
        name="postsale_return",
        description="用户申请退货退款或售后退款",
        required_slots=[
            SlotDef(
                name="order_id",
                description="订单号",
                ask_prompt="请选择要申请售后的订单",
            ),
            SlotDef(
                name="postsale_type",
                description="售后类型：仅退款或退货退款",
                ask_prompt="请选择售后方式",
            ),
            SlotDef(
                name="postsale_reason",
                description="售后原因",
                ask_prompt="请选择售后原因",
            ),
        ],
        handler=PostsaleReturnHandler,
    ),
    IntentDefinition(
        name="product_inquiry",
        description="用户咨询商品信息，包括商品价格、规格、库存、使用说明等",
        required_slots=[
            SlotDef(
                name="query",
                description="用户的原始问题",
                ask_prompt="请问您想了解什么商品信息？",
            ),
        ],
        handler=ProductInquiryHandler,
    ),
]
