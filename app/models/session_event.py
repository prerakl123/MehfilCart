"""SessionEvent model -- persistent audit log of everything that happens in a session."""

import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class SessionEventType(str, enum.Enum):
    """Kinds of events recorded in a session's audit timeline."""
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STATUS_CHANGED = "SESSION_STATUS_CHANGED"
    SESSION_CLOSED = "SESSION_CLOSED"
    MEMBER_JOIN_REQUESTED = "MEMBER_JOIN_REQUESTED"
    MEMBER_APPROVED = "MEMBER_APPROVED"
    MEMBER_REJECTED = "MEMBER_REJECTED"
    MEMBER_LEFT = "MEMBER_LEFT"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    SERVICE_ACTION_REQUESTED = "SERVICE_ACTION_REQUESTED"
    SERVICE_ACTION_CLAIMED = "SERVICE_ACTION_CLAIMED"
    SERVICE_ACTION_COMPLETED = "SERVICE_ACTION_COMPLETED"


class SessionEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A single recorded event in a session's lifecycle, used to render an audit timeline."""
    __tablename__ = "session_events"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[SessionEventType] = mapped_column(
        SAEnum(SessionEventType, name="session_event_type"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    session = relationship("Session", lazy="selectin")
    actor = relationship("User", lazy="selectin")

    @property
    def actor_name(self) -> str | None:
        """Display name of the user who triggered this event, if available."""
        return self.actor.display_name if self.actor else None

    def __repr__(self):
        """Return a human-readable representation of the SessionEvent instance."""
        return f"<SessionEvent {self.event_type} session={self.session_id}>"
