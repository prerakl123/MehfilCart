"""Menu schemas -- category and item CRUD."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.models.menu import DietType


class CategoryCreate(BaseModel):
    """Request to create a menu category."""
    name: str = Field(..., min_length=1, max_length=50)
    display_order: int = 0
    icon: str | None = None


class CategoryUpdate(BaseModel):
    """Partial update to a category."""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    display_order: int | None = None
    icon: str | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    """Category in API responses."""
    id: UUID
    restaurant_id: UUID
    name: str
    display_order: int
    icon: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    """Request to create a menu item."""
    category_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    price: float = Field(..., gt=0)
    image_url: str | None = None
    diet_type: DietType = DietType.VEG
    customizations: dict | None = None
    display_order: int = 0


class MenuItemUpdate(BaseModel):
    """Partial update to a menu item."""
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    price: float | None = Field(default=None, gt=0)
    image_url: str | None = None
    diet_type: DietType | None = None
    is_available: bool | None = None
    customizations: dict | None = None
    display_order: int | None = None


class MenuItemResponse(BaseModel):
    """Menu item in API responses."""
    id: UUID
    category_id: UUID
    category_name: str | None = None
    name: str
    description: str | None
    price: float
    image_url: str | None
    diet_type: DietType
    is_available: bool
    customizations: dict | None
    display_order: int

    model_config = {"from_attributes": True}


class MenuResponse(BaseModel):
    """Full restaurant menu grouped by category."""
    restaurant_id: UUID
    categories: list[CategoryResponse] = []
    items: list[MenuItemResponse] = []
