"""User profile schemas -- profile view/update and name change requests."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """Current user profile."""
    id: UUID
    phone: str
    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    restaurant_id: UUID | None = None

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """Request body to update user profile."""
    display_name: str = Field(..., min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=100)


class NameChangeRequestResponse(BaseModel):
    """Staff name change request in API responses."""
    id: UUID
    user_id: UUID
    restaurant_id: UUID
    requested_name: str
    status: str
    user_phone: str | None = None
    current_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
