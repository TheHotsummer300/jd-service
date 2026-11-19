"""电商业务 ORM 模型 — 映射已有 ecs 库中的表

对应 docker/mysql/ecs.sql 中定义的表结构。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class EcommerceBase(DeclarativeBase):
    """电商业务线 ORM 基类（独立于平台库 Base）"""
    pass


class OrderInfo(EcommerceBase):
    """订单信息表 — 映射 order_info"""
    __tablename__ = "order_info"

    order_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    create_time: Mapped[datetime] = mapped_column(DateTime)
    payment_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    complete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user_info.user_id"))
    receive_id: Mapped[str] = mapped_column(String(50), ForeignKey("receive_info.receive_id"))
    order_status: Mapped[str] = mapped_column(String(20), ForeignKey("order_status.order_status"))

    details = relationship("OrderDetail", back_populates="order", lazy="selectin")


class OrderDetail(EcommerceBase):
    """订单明细表 — 映射 order_detail"""
    __tablename__ = "order_detail"

    order_detail_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(50), ForeignKey("order_info.order_id"))
    sku_id: Mapped[str] = mapped_column(String(50), ForeignKey("sku_info.sku_id"))
    sku_name: Mapped[str] = mapped_column(String(100))
    sku_count: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    final_amount: Mapped[float] = mapped_column(Numeric(10, 2))

    order = relationship("OrderInfo", back_populates="details")


class SkuInfo(EcommerceBase):
    """商品信息表 — 映射 sku_info"""
    __tablename__ = "sku_info"

    sku_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    sku_name: Mapped[str] = mapped_column(String(100))
    sku_price: Mapped[float] = mapped_column(Numeric(10, 2))
    sku_category: Mapped[str] = mapped_column(String(20))
    sku_count: Mapped[int] = mapped_column(Integer)


class Postsale(EcommerceBase):
    """售后表 — 映射 postsale"""
    __tablename__ = "postsale"

    postsale_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    create_time: Mapped[datetime] = mapped_column(DateTime)
    complete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_detail_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("order_detail.order_detail_id")
    )
    refund_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)
    postsale_type: Mapped[str] = mapped_column(String(10))  # 退款/退货/换货
    postsale_reason: Mapped[str] = mapped_column(String(500))
    postsale_status: Mapped[str] = mapped_column(
        String(20), ForeignKey("postsale_status.postsale_status")
    )
    receive_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("receive_info.receive_id")
    )
