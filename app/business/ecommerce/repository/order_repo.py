"""订单数据访问层

使用电商业务线独立的数据库引擎和 session。
"""
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from loguru import logger

from app.business.ecommerce.config import ecommerce_settings
from app.business.ecommerce.models.order import OrderInfo, OrderDetail, SkuInfo, Postsale

# 电商业务线独立的数据库引擎
eco_engine = create_async_engine(
    ecommerce_settings.eco_database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
)

EcoSessionLocal = async_sessionmaker(
    bind=eco_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class OrderRepo:
    """订单数据仓库

    提供订单、订单明细、商品信息的查询和写入能力。
    """

    async def get_orders_by_user(
        self, user_id: str, limit: int = 10
    ) -> list[OrderInfo]:
        """查询用户最近的订单，按创建时间倒序"""
        async with EcoSessionLocal() as db:
            result = await db.execute(
                select(OrderInfo)
                .where(OrderInfo.user_id == user_id)
                .order_by(OrderInfo.create_time.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_order_by_id(self, order_id: str) -> OrderInfo | None:
        """按订单 ID 查询订单（含明细）"""
        async with EcoSessionLocal() as db:
            result = await db.execute(
                select(OrderInfo).where(OrderInfo.order_id == order_id)
            )
            return result.scalar_one_or_none()

    async def get_order_detail_by_order(
        self, order_id: str
    ) -> list[OrderDetail]:
        """查询订单的所有明细"""
        async with EcoSessionLocal() as db:
            result = await db.execute(
                select(OrderDetail).where(OrderDetail.order_id == order_id)
            )
            return list(result.scalars().all())

    async def get_sku_by_id(self, sku_id: str) -> SkuInfo | None:
        """按 SKU ID 查询商品信息"""
        async with EcoSessionLocal() as db:
            result = await db.execute(
                select(SkuInfo).where(SkuInfo.sku_id == sku_id)
            )
            return result.scalar_one_or_none()

    async def get_postable_reasons(
        self, product_category: str | None = None
    ) -> list[str]:
        """获取可用的售后原因列表，可按商品类别筛选"""
        async with EcoSessionLocal() as db:
            # 注意：postsale_reason 表通过另一个引擎访问复杂，这里简化为固定清单
            # 实际业务中 postsale_reason 表存储了所有售后原因
            pass  # 由 handler 层提供

    async def update_order_status(
        self, order_id: str, new_status: str
    ) -> None:
        """更新订单状态"""
        async with EcoSessionLocal() as db:
            await db.execute(
                update(OrderInfo)
                .where(OrderInfo.order_id == order_id)
                .values(order_status=new_status)
            )
            await db.commit()
            logger.info(f"订单状态更新: {order_id} → {new_status}")

    async def create_postsale(
        self,
        order_detail_id: str,
        refund_amount: float,
        postsale_type: str,
        postsale_reason: str,
        receive_id: str,
    ) -> Postsale:
        """创建售后记录并更新订单状态为售后中"""
        async with EcoSessionLocal() as db:
            # 创建售后记录
            postsale = Postsale(
                postsale_id=str(uuid.uuid4()),
                create_time=datetime.now(),
                order_detail_id=order_detail_id,
                refund_amount=refund_amount,
                postsale_type=postsale_type,
                postsale_reason=postsale_reason,
                postsale_status="审核中",
                receive_id=receive_id,
            )
            db.add(postsale)

            # 更新关联订单状态为"售后中"
            # 先查明细找到订单ID
            result = await db.execute(
                select(OrderDetail).where(
                    OrderDetail.order_detail_id == order_detail_id
                )
            )
            detail = result.scalar_one_or_none()
            if detail:
                await db.execute(
                    update(OrderInfo)
                    .where(OrderInfo.order_id == detail.order_id)
                    .values(order_status="售后中")
                )

            await db.commit()
            await db.refresh(postsale)
            logger.info(
                f"创建售后记录: {postsale.postsale_id}, "
                f"类型: {postsale_type}, 原因: {postsale_reason}"
            )
            return postsale
