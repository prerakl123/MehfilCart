"""Menu models -- Category and MenuItem."""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class DietType(str, enum.Enum):
    VEG = "VEG"
    NON_VEG = "NON_VEG"
    VEGAN = "VEGAN"
    EGGETARIAN = "EGGETARIAN"


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A menu category (e.g., Starters, Beverages) within a restaurant."""
    __tablename__ = "categories"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="categories")
    items = relationship(
        "MenuItem", back_populates="category", lazy="selectin")

    def __repr__(self):
        return f"<Category {self.name}>"


class MenuItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An individual menu item within a category."""
    __tablename__ = "menu_items"

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    diet_type: Mapped[DietType] = mapped_column(
        SAEnum(DietType, name="diet_type"),
        default=DietType.VEG,
        nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)
    customizations: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False)

    # Relationships
    category = relationship("Category", back_populates="items")

    def __repr__(self):
        return f"<MenuItem {self.name} price={self.price}>"
