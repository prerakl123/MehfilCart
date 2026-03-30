"""Restaurant and UserRole models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class Restaurant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A restaurant registered on the platform."""
    __tablename__ = "restaurants"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)

    # Relationships
    tables = relationship(
        "Table", back_populates="restaurant", lazy="selectin")
    categories = relationship(
        "Category", back_populates="restaurant", lazy="selectin")
    user_roles = relationship(
        "UserRole", back_populates="restaurant", lazy="selectin")

    def __repr__(self):
        """Return a human-readable representation of the Restaurant instance."""
        return f"<Restaurant {self.name}>"


class UserRole(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Maps users to roles within a specific restaurant context."""
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(30), nullable=False)  # Values from permissions.Role

    # Relationships
    user = relationship("User", back_populates="user_roles")
    restaurant = relationship("Restaurant", back_populates="user_roles")

    def __repr__(self):
        """Return a human-readable representation of the UserRole instance."""
        return f"<UserRole {self.role} user={self.user_id} restaurant={self.restaurant_id}>"
