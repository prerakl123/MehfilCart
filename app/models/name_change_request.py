"""NameChangeRequest model -- tracks staff display name change requests."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class NameChangeStatus(str, enum.Enum):
    """Review state of a staff display name change request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class NameChangeRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A request from a staff member to change their display name."""
    __tablename__ = "name_change_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("restaurants.id"), nullable=False, index=True)
    requested_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[NameChangeStatus] = mapped_column(Enum(NameChangeStatus), default=NameChangeStatus.PENDING, nullable=False)

    # Relationships
    user = relationship("User", lazy="selectin")
    restaurant = relationship("Restaurant", lazy="selectin")
