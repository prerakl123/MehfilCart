"""ServiceAction model for guest quick actions."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class ActionType(str, enum.Enum):
    """Types of service actions guests can request."""
    CALL_WAITER = "CALL_WAITER"
    TABLE_CLEANUP = "TABLE_CLEANUP"
    WATER_REFILL = "WATER_REFILL"
    BILL_REQUEST = "BILL_REQUEST"
    EXTRA_CUTLERY = "EXTRA_CUTLERY"


class ActionStatus(str, enum.Enum):
    """Lifecycle states of a service action."""
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"


class ServiceAction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A quick action request from a table session (e.g., Call Waiter)."""
    __tablename__ = "service_actions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False, index=True
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id"), nullable=False, index=True
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tables.id"), nullable=False, index=True
    )
    action_type: Mapped[ActionType] = mapped_column(
        SAEnum(ActionType, name="action_type_enum"), nullable=False
    )
    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, name="action_status_enum"), default=ActionStatus.PENDING, nullable=False
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    claimed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    session = relationship("Session", lazy="selectin")
    restaurant = relationship("Restaurant", lazy="selectin")
    table = relationship("Table", lazy="selectin")
    requested_by = relationship("User", foreign_keys=[requested_by_id], lazy="selectin")
    claimed_by = relationship("User", foreign_keys=[claimed_by_id], lazy="selectin")

    def __repr__(self):
        """Return a human-readable representation of the ServiceAction instance."""
        return f"<ServiceAction {self.action_type} table={self.table_id} status={self.status}>"
