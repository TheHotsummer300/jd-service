"""订单查询意图处理器"""
from loguru import logger

from app.business.base import (
    IntentHandler,
    BusinessContext,
    BusinessResult,
    OptionItem,
)
from app.business.ecommerce.models.order import OrderInfo


def _build_order_label(o: OrderInfo) -> str:
    """构造订单按钮的展示文案 — 时间 + 商品 + 状态"""
    create_date = o.create_time.strftime("%m-%d %H:%M") if o.create_time else "未知"
    # 从关联的 details 中取商品名（已 eager load selectin）
    product_names = ", ".join(d.sku_name for d in (o.details or [])[:2])
    if len(o.details or []) > 2:
        product_names += " 等"
    if not product_names:
        product_names = "未知商品"
    return f"[{create_date}] {product_names}（{o.order_status}）"


class OrderQueryHandler(IntentHandler):
    """订单查询处理器

    槽位驱动：order_id 缺失时返回用户最近订单列表让用户选。
    """

    def __init__(self, repo=None):
        from app.business.ecommerce.repository.order_repo import OrderRepo
        self._repo = repo if repo is not None else OrderRepo()

    async def handle(self, ctx: BusinessContext) -> BusinessResult:
        order_id = str(ctx.slots.get("order_id", ""))
        if not order_id:
            return await self._ask_for_order(ctx)
        return await self._query(ctx)

    async def _ask_for_order(self, ctx: BusinessContext) -> BusinessResult:
        """order_id 缺失：返回用户最近订单"""
        try:
            orders = await self._repo.get_orders_by_user(ctx.user_id, limit=5)
            options = [
                OptionItem(
                    label=_build_order_label(o),
                    value=o.order_id,
                )
                for o in orders
            ]
            logger.info(f"订单查询-返回订单列表: user={ctx.user_id}, 订单数={len(options)}")
            return BusinessResult.ask_slot(
                slot_to_fill="order_id",
                options=options,
                message="请选择要查询的订单",
            )
        except Exception as e:
            logger.error(f"查询用户订单失败: {e}")
            return BusinessResult.error("查询订单时出现错误，请稍后重试")

    async def _query(self, ctx: BusinessContext) -> BusinessResult:
        """order_id 齐全：查询订单详情"""
        order_id = str(ctx.slots.get("order_id", ""))

        try:
            order = await self._repo.get_order_by_id(order_id)
            if order is None:
                return BusinessResult.error(
                    f"订单 {order_id} 不存在，请确认订单号是否正确"
                )

            details = await self._repo.get_order_detail_by_order(order_id)

            detail_list = []
            for d in details:
                sku = await self._repo.get_sku_by_id(d.sku_id)
                detail_list.append({
                    "sku_id": d.sku_id,
                    "sku_name": d.sku_name,
                    "sku_count": d.sku_count,
                    "unit_price": float(sku.sku_price) if sku else 0,
                    "total_amount": float(d.total_amount),
                    "discount_amount": float(d.discount_amount),
                    "final_amount": float(d.final_amount),
                })

            order_data = {
                "order_id": order.order_id,
                "order_status": order.order_status,
                "create_time": order.create_time.isoformat() if order.create_time else "",
                "payment_time": order.payment_time.isoformat() if order.payment_time else "",
                "delivered_time": order.delivered_time.isoformat() if order.delivered_time else "",
                "details": detail_list,
            }

            logger.info(f"订单查询成功: {order_id}")
            # 把详情拼成可见文本
            status_text = f"订单状态：{order.order_status}"
            time_text = f"创建时间：{order.create_time.strftime('%Y-%m-%d %H:%M') if order.create_time else '未知'}"
            lines = [f"📋 订单 {order_id}", status_text, time_text, "", "商品明细："]
            total_price = 0.0
            for i, d in enumerate(detail_list, 1):
                sku = await self._repo.get_sku_by_id(d["sku_id"])
                price = float(sku.sku_price) if sku else 0.0
                final = float(d["final_amount"])
                total_price += final
                lines.append(f"  {i}. {d['sku_name']} ×{d['sku_count']}  单价 ¥{price:.2f}  实付 ¥{final:.2f}")
            lines.append(f"\n合计：¥{total_price:.2f}")
            return BusinessResult.completed(
                message="\n".join(lines),
                **order_data,
            )

        except Exception as e:
            logger.error(f"订单查询失败: {e}")
            return BusinessResult.error("查询订单时出现错误，请稍后重试")
