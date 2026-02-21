"""Session schemas -- create, update, join, member management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.session import SessionStatus, MemberRole, MemberStatus


class SessionCreate(BaseModel):
    """Request to create a new session at a table."""
    table_id: UUID


class SessionUpdate(BaseModel):
    """Partial update to a session (lock, toggle additions)."""
    allow_additions: bool | None = None
    status: SessionStatus | None = None


class SessionMemberResponse(BaseModel):
    """A session member in API responses."""
    id: UUID
    user_id: UUID
    display_name: str | None
    phone: str
    role: MemberRole
    status: MemberStatus
    joined_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Full session details in API responses."""
    id: UUID
    table_id: UUID
    table_label: str | None = None
    host_user_id: UUID
    status: SessionStatus
    allow_additions: bool
    started_at: datetime
    expires_at: datetime
    closed_at: datetime | None
    members: list[SessionMemberResponse] = []

    model_config = {"from_attributes": True}


class MemberActionRequest(BaseModel):
    """Host action on a pending member (approve or reject)."""
    action: str = Field(..., pattern="^(approve|reject)$")


class SessionReopenRequest(BaseModel):
    """Admin request to reopen a timed-out session with optional new timeout."""
    new_timeout_minutes: int | None = None
