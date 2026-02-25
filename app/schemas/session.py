"""Session schemas -- create, update, join, member management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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
    display_name: str | None = None
    phone: str | None = None
    role: MemberRole
    status: MemberStatus
    joined_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_user_fields(cls, data):
        """Pull display_name and phone from the related User object."""
        try:
            from sqlalchemy import inspect as sa_inspect
            insp = sa_inspect(data)
            if "user" in insp.dict and data.user is not None:
                if not getattr(data, "display_name", None):
                    data.display_name = data.user.display_name
                if not getattr(data, "phone", None):
                    data.phone = data.user.phone
        except Exception:
            pass
        return data


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

    @model_validator(mode="before")
    @classmethod
    def extract_table_label(cls, data):
        """Pull table label from the related Table object."""
        try:
            from sqlalchemy import inspect as sa_inspect
            insp = sa_inspect(data)
            # Only access 'table' if it's already loaded (not pending lazy load)
            if "table" in insp.dict and data.table is not None:
                data.table_label = data.table.label
        except Exception:
            pass
        return data


class MemberActionRequest(BaseModel):
    """Host action on a pending member (approve or reject)."""
    action: str = Field(..., pattern="^(approve|reject)$")


class SessionReopenRequest(BaseModel):
    """Admin request to reopen a timed-out session with optional new timeout."""
    new_timeout_minutes: int | None = None
