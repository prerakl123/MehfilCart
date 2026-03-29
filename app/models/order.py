"""Order and OrderItem models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class OrderStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PREPARING = "PREPARING"
    READY = "READY"
    SERVED = "SERVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A submitted food order from a session."""
    __tablename__ = "orders"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status"),
        default=OrderStatus.RECEIVED,
        nullable=False,
    )
    special_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="orders")
    submitter = relationship("User", foreign_keys=[submitted_by])
    canceller = relationship("User", foreign_keys=[cancelled_by])
    items = relationship("OrderItem", back_populates="order", lazy="selectin")

    @property
    def submitter_name(self) -> str | None:
        return self.submitter.display_name if self.submitter else None

    def __repr__(self):
        return f"<Order {self.id} status={self.status} total={self.total_amount}>"


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An individual item within an order, attributed to the user who added it."""
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("menu_items.id"), nullable=False
    )
    added_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    customizations: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")
    adder = relationship("User", foreign_keys=[added_by])

    @property
    def added_by_id(self):
        return self.added_by

    @property
    def added_by_name(self) -> str | None:
        return self.adder.display_name if self.adder else None

    @property
    def menu_item_name(self) -> str:
        return self.menu_item.name if self.menu_item else "Unknown"

    def __repr__(self):
        return f"<OrderItem menu_item={self.menu_item_id} qty={self.quantity}>"
