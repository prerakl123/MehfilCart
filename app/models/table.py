"""Table model -- represents physical dining tables within a restaurant."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class Table(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tables"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(
        String(20), nullable=False)  # e.g., "T1", "A5"
    qr_code_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="tables")
    sessions = relationship("Session", back_populates="table", lazy="selectin")

    def __repr__(self):
        return f"<Table {self.label} restaurant={self.restaurant_id}>"
