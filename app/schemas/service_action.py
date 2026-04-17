"""Service action schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.service_action import ActionType, ActionStatus


class ServiceActionCreate(BaseModel):
    """Request to create a new service action."""
    action_type: ActionType


class ServiceActionResponse(BaseModel):
    """Service action in API responses."""
    id: UUID
    session_id: UUID
    restaurant_id: UUID
    table_id: UUID
    action_type: ActionType
    status: ActionStatus
    requested_by_id: UUID
    claimed_by_id: UUID | None
    created_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None

    # Enriched fields for UI
    table_label: str | None = None
    requested_by_name: str | None = None
    claimed_by_name: str | None = None

    model_config = {"from_attributes": True}
