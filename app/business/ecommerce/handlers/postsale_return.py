"""售后申请意图处理器

槽位驱动的逐槽位填充流程：
  1. 缺少 order_id   → 返回最近订单列表让用户选
  2. 缺少 postsale_type  → 返回售后方式选项
  3. 缺少 postsale_reason → 返回售后原因选项
  4. 三个槽位齐全      → 修改订单状态为"售后中"
"""
from loguru import logger

from app.business.base import (
    IntentHandler,
    BusinessContext,
    BusinessResult,
    OptionItem,
)
from app.business.ecommerce.models.order import OrderInfo

# 可售后的订单状态
_REFUNDABLE_STATUSES = frozenset({"已付款", "已发货", "已签收"})

# 售后方式
_POSTSALE_TYPES = {
    "refund_only": "仅退款",
    "return_refund": "退货退款",
}

# 售后方式反向映射（中文 label → 内部 key），用于 NLU 翻译后的兜底规范化
_LABEL_TO_TYPE: dict[str, str] = {v: k for k, v in _POSTSALE_TYPES.items()}

# 售后原因
_POSTSALE_REASONS = [
    "7天无理由",
    "商品瑕疵/破损",
    "发错货",
    "商品与描述不符",
    "质量问题",
    "不喜欢/不想要了",
]


def _build_order_label(o: OrderInfo) -> str:
    """构造订单按钮的展示文案 — 时间 + 商品 + 状态"""
    create_date = o.create_time.strftime("%m-%d %H:%M") if o.create_time else "未知"
    product_names = ", ".join(d.sku_name for d in (o.details or [])[:2])
    if len(o.details or []) > 2:
        product_names += " 等"
    if not product_names:
        product_names = "未知商品"
    return f"[{create_date}] {product_names}（{o.order_status}）"


def _normalize_postsale_type(raw: str) -> str | None:
    """将 postsale_type 规范化为内部 key

    NLU 可能把内部 key（如 "return_refund"）"理解"成中文 label（"退货退款"），
    因此需要反向映射兜底。已匹配的内部 key 直接返回。
    """
    # 已是合法内部 key，直接返回
    if raw in _POSTSALE_TYPES:
        return raw
    # 可能是中文 label，做反向映射
    if raw in _LABEL_TO_TYPE:
        return _LABEL_TO_TYPE[raw]
    return None


class PostsaleReturnHandler(IntentHandler):
    """售后申请处理器"""

    def __init__(self, repo=None):
        from app.business.ecommerce.repository.order_repo import OrderRepo
        self._repo = repo if repo is not None else OrderRepo()

    async def handle(self, ctx: BusinessContext) -> BusinessResult:
        slots = ctx.slots

        if not slots.get("order_id"):
            return await self._ask_for_order(ctx)
        if not slots.get("postsale_type"):
            order_check = await self._check_order(ctx)
            if not order_check.success:
                return order_check
            return self._ask_for_type()
        if not slots.get("postsale_reason"):
            return self._ask_for_reason()

        return await self._execute(ctx)

    async def _ask_for_order(self, ctx: BusinessContext) -> BusinessResult:
        try:
            orders = await self._repo.get_orders_by_user(ctx.user_id, limit=5)
            options = [
                OptionItem(
                    label=_build_order_label(o),
                    value=o.order_id,
                    disabled=o.order_status not in _REFUNDABLE_STATUSES,
                )
                for o in orders
            ]
            logger.info(f"售后-返回订单列表: user={ctx.user_id}, 订单数={len(options)}")
            return BusinessResult.ask_slot(
                slot_to_fill="order_id",
                options=options,
                message="请选择要申请售后的订单",
            )
        except Exception as e:
            logger.error(f"查询用户订单失败: {e}")
            return BusinessResult.error("查询订单时出现错误，请稍后重试")

    def _ask_for_type(self) -> BusinessResult:
        options = [
            OptionItem(label=v, value=k)
            for k, v in _POSTSALE_TYPES.items()
        ]
        return BusinessResult.ask_slot(
            slot_to_fill="postsale_type",
            options=options,
            message="请选择售后方式",
        )

    def _ask_for_reason(self) -> BusinessResult:
        options = [
            OptionItem(label=r, value=r)
            for r in _POSTSALE_REASONS
        ]
        return BusinessResult.ask_slot(
            slot_to_fill="postsale_reason",
            options=options,
            message="请选择售后原因",
        )

    async def _check_order(self, ctx: BusinessContext) -> BusinessResult:
        order_id = str(ctx.slots.get("order_id", ""))
        try:
            order = await self._repo.get_order_by_id(order_id)
            if order is None:
                return BusinessResult.error(f"订单 {order_id} 不存在，请确认订单号")
            if order.user_id != ctx.user_id:
                return BusinessResult.error("该订单不属于当前用户")
            if order.order_status not in _REFUNDABLE_STATUSES:
                return BusinessResult.error(
                    f"订单状态为「{order.order_status}」，"
                    f"仅已付款/已发货/已签收的订单可申请售后"
                )
            return BusinessResult(success=True)
        except Exception as e:
            logger.error(f"校验订单失败: {e}")
            return BusinessResult.error("查询订单时出现错误，请稍后重试")

    async def _execute(self, ctx: BusinessContext) -> BusinessResult:
        order_id = str(ctx.slots.get("order_id", ""))
        postsale_type = str(ctx.slots.get("postsale_type", "refund_only"))
        postsale_reason = str(ctx.slots.get("postsale_reason", ""))

        # 规范化 postsale_type：NLU 可能将内部 key 翻译为中文 label，做反向映射兜底
        postsale_type = _normalize_postsale_type(postsale_type)
        if postsale_type is None:
            return BusinessResult.error(
                f"不支持的售后方式: {ctx.slots.get('postsale_type', '')}"
            )

        order_check = await self._check_order(ctx)
        if not order_check.success:
            return order_check

        try:
            await self._repo.update_order_status(order_id, "售后中")
            type_label = _POSTSALE_TYPES[postsale_type]
            logger.info(
                f"售后完成: 订单={order_id}, "
                f"方式={type_label}, 原因={postsale_reason}"
            )
            return BusinessResult.completed(
                message=(
                    f"售后申请已提交！\n"
                    f"订单号：{order_id}\n"
                    f"售后方式：{type_label}\n"
                    f"售后原因：{postsale_reason}\n"
                    f"当前状态：售后中"
                ),
                order_id=order_id,
                postsale_type=type_label,
                postsale_reason=postsale_reason,
                new_status="售后中",
            )
        except Exception as e:
            logger.error(f"售后执行失败: {e}")
            return BusinessResult.error("处理售后申请时出现错误，请稍后重试")
