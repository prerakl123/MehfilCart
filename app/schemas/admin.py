"""Admin schemas -- dashboard, table management, staff management, config."""

from uuid import UUID

from pydantic import BaseModel, Field


class TableCreate(BaseModel):
    """Request to create a new table."""
    label: str = Field(..., min_length=1, max_length=20)
    capacity: int = Field(default=4, ge=1, le=50)


class TableUpdate(BaseModel):
    """Partial update to a table."""
    label: str | None = Field(default=None, min_length=1, max_length=20)
    capacity: int | None = Field(default=None, ge=1, le=50)
    is_active: bool | None = None


class TableResponse(BaseModel):
    """Table in API responses."""
    id: UUID
    restaurant_id: UUID
    label: str
    qr_code_url: str | None
    capacity: int
    is_active: bool

    model_config = {"from_attributes": True}


class StaffCreate(BaseModel):
    """Request to add a staff member to a restaurant."""
    phone: str = Field(..., min_length=10, max_length=15)
    role: str = Field(default="WAITER", pattern="^(WAITER|RESTAURANT_ADMIN)$")
    display_name: str | None = None


class StaffResponse(BaseModel):
    """Staff member in API responses."""
    id: UUID
    user_id: UUID
    phone: str
    display_name: str | None
    role: str
    restaurant_id: UUID

    model_config = {"from_attributes": True}


class RestaurantConfigUpdate(BaseModel):
    """Update restaurant-level configuration."""
    session_timeout_minutes: int | None = Field(default=None, ge=5, le=180)
    max_guests_per_session: int | None = Field(default=None, ge=1, le=50)
    reopen_window_minutes: int | None = Field(default=None, ge=5, le=60)
    idle_timeout_minutes: int | None = Field(default=None, ge=5, le=60)


class DashboardStats(BaseModel):
    """Admin dashboard overview statistics."""
    active_sessions: int = 0
    total_orders_today: int = 0
    revenue_today: float = 0.0
    total_tables: int = 0
    active_staff: int = 0
