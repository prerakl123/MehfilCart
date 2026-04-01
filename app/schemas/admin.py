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


class HourlyMetric(BaseModel):
    time: str
    revenue: float
    orders: int

class CategoryMetric(BaseModel):
    category: str
    revenue: float
    percentage: float

class ItemMetric(BaseModel):
    name: str
    orders: int
    revenue: float

class RestaurantPerformanceMetric(BaseModel):
    id: UUID
    name: str
    revenue: float
    orders: int

class DailyPlatformMetric(BaseModel):
    date: str
    revenue: float
    orders: int

class RestaurantDashboardStats(BaseModel):
    """Restaurant Admin dashboard comprehensive statistics."""
    # Top Level
    revenue_today: float
    revenue_trend: float  # percentage change from same day last week
    orders_today: int
    orders_trend: float   # percentage change from same day last week
    active_sessions: int
    total_tables: int
    active_tables: int
    table_occupancy_rate: float
    
    # Chart Data
    hourly_trend: list[HourlyMetric] = Field(default_factory=list)
    category_sales: list[CategoryMetric] = Field(default_factory=list)
    top_items: list[ItemMetric] = Field(default_factory=list)
    dead_stock: list[ItemMetric] = Field(default_factory=list)
    
    # Operational
    live_orders_preparing: int
    live_orders_ready: int
    average_order_value: float

class SuperAdminDashboardStats(BaseModel):
    """Super Admin global dashboard statistics."""
    # Top Level
    total_gmv_today: float
    gmv_trend: float      # percentage change from same day last week
    total_active_restaurants: int
    total_orders_today: int
    global_active_sessions: int
    
    # Restaurant Performance
    top_restaurants: list[RestaurantPerformanceMetric] = Field(default_factory=list)
    lowest_restaurants: list[RestaurantPerformanceMetric] = Field(default_factory=list)
    
    # Chart Data
    global_hourly_trend: list[HourlyMetric] = Field(default_factory=list)
    platform_growth_trend: list[DailyPlatformMetric] = Field(default_factory=list)
