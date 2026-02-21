"""Restaurant schemas -- CRUD for platform restaurant management."""

from uuid import UUID

from pydantic import BaseModel, Field


class RestaurantCreate(BaseModel):
    """Request to register a new restaurant on the platform."""
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100,
                      pattern="^[a-z0-9-]+$")
    address: str | None = None
    phone: str | None = Field(default=None, min_length=10, max_length=15)
    logo_url: str | None = None


class RestaurantUpdate(BaseModel):
    """Partial update to a restaurant."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1,
                             max_length=100, pattern="^[a-z0-9-]+$")
    address: str | None = None
    phone: str | None = Field(default=None, min_length=10, max_length=15)
    logo_url: str | None = None
    is_active: bool | None = None


class RestaurantResponse(BaseModel):
    """Restaurant in API responses."""
    id: UUID
    name: str
    slug: str
    address: str | None
    phone: str | None
    logo_url: str | None
    config: dict | None
    is_active: bool

    model_config = {"from_attributes": True}
