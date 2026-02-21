"""Cart schemas -- add, update, and display cart items."""

from uuid import UUID

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    """Request to add an item to the session cart."""
    menu_item_id: UUID
    quantity: int = Field(default=1, ge=1, le=50)
    customizations: dict | None = None
    notes: str | None = None


class CartItemUpdate(BaseModel):
    """Request to update a cart item's quantity or customizations."""
    quantity: int | None = Field(default=None, ge=1, le=50)
    customizations: dict | None = None
    notes: str | None = None


class CartItemResponse(BaseModel):
    """A single item in the cart with user attribution."""
    id: UUID
    menu_item_id: UUID
    menu_item_name: str
    menu_item_price: float
    added_by_id: UUID
    added_by_name: str | None
    quantity: int
    customizations: dict | None
    notes: str | None

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    """Full cart state for a session."""
    session_id: UUID
    items: list[CartItemResponse] = []
    total: float = 0.0
    item_count: int = 0
