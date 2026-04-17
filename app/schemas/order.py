"""Order schemas -- submission, status update, and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class OrderSubmit(BaseModel):
    """Request to submit the current cart as a finalized order."""
    special_notes: str | None = None


class OrderStatusUpdate(BaseModel):
    """Request to update an order's status (staff/admin only)."""
    status: OrderStatus


class OrderCancelRequest(BaseModel):
    """Request to cancel an order with a reason."""
    reason: str = Field(..., min_length=3, max_length=500)


class OrderItemResponse(BaseModel):
    """A single item within an order response."""
    id: UUID
    menu_item_id: UUID
    menu_item_name: str
    added_by_id: UUID
    added_by_name: str | None
    quantity: int
    unit_price: float
    customizations: dict | None
    notes: str | None
    prep_time_minutes: int | None = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Full order details in API responses."""
    id: UUID
    session_id: UUID
    status: OrderStatus
    special_notes: str | None
    submitted_at: datetime
    submitted_by: UUID
    submitter_name: str | None = None
    total_amount: float
    cancelled_by: UUID | None
    cancel_reason: str | None
    table_label: str | None = None
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """Paginated list of orders."""
    orders: list[OrderResponse] = []
    total: int = 0
