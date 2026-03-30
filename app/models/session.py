"""Session and SessionMember models -- the collaborative ordering session."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class SessionStatus(str, enum.Enum):
    """Lifecycle states a collaborative ordering session can be in."""
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    TIMED_OUT = "TIMED_OUT"
    SUBMITTED = "SUBMITTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class MemberRole(str, enum.Enum):
    """Role a participant holds within a session — either the originating Host or a Guest."""
    HOST = "HOST"
    GUEST = "GUEST"


class MemberStatus(str, enum.Enum):
    """Approval state of a session membership request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    LEFT = "LEFT"


class Session(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A collaborative ordering session at a table."""
    __tablename__ = "sessions"

    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tables.id"), nullable=False, index=True
    )
    host_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status"),
        default=SessionStatus.CREATED,
        nullable=False,
    )
    allow_additions: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    # Relationships
    table = relationship("Table", back_populates="sessions")
    host = relationship("User", foreign_keys=[host_user_id])
    members = relationship(
        "SessionMember", back_populates="session", lazy="selectin")
    orders = relationship("Order", back_populates="session", lazy="selectin")

    def __repr__(self):
        """Return a human-readable representation of the Session instance."""
        return f"<Session {self.id} status={self.status} table={self.table_id}>"


class SessionMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A user's membership in a session."""
    __tablename__ = "session_members"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[MemberRole] = mapped_column(
        SAEnum(MemberRole, name="member_role"),
        nullable=False,
    )
    status: Mapped[MemberStatus] = mapped_column(
        SAEnum(MemberStatus, name="member_status"),
        default=MemberStatus.PENDING,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)

    # Relationships
    session = relationship("Session", back_populates="members")
    user = relationship("User", back_populates="session_memberships")

    def __repr__(self):
        """Return a human-readable representation of the SessionMember instance."""
        return f"<SessionMember {self.role} user={self.user_id} session={self.session_id}>"
