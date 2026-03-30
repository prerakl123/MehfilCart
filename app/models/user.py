"""User model -- represents all platform users (guests, staff, admins)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents every person that interacts with the platform — guests, staff, and admins alike."""
    __tablename__ = "users"

    phone: Mapped[str] = mapped_column(
        String(15), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    # Relationships
    user_roles = relationship(
        "UserRole", back_populates="user", lazy="selectin")
    session_memberships = relationship(
        "SessionMember", back_populates="user", lazy="selectin")

    def __repr__(self):
        """Return a human-readable representation of the User instance."""
        return f"<User {self.phone} ({self.display_name})>"
