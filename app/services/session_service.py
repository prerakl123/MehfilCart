"""
Session service -- create, join, manage members, timeout enforcement, reopen.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException, ConflictException, ForbiddenException,
    NotFoundException, SessionExpiredException, SessionLockedException,
)
from app.models.session import (
    MemberRole, MemberStatus, Session, SessionMember, SessionStatus,
)
from app.models.table import Table
from app.models.user import User


async def create_session(db: AsyncSession, user: User, table_id: UUID) -> Session:
    """
    Create a new ordering session at a table. The user becomes the Host.
    Ensures no other active session exists at the same table.
    """
    # Verify table exists and is active
    result = await db.execute(select(Table).where(Table.id == table_id))
    table = result.scalar_one_or_none()
    if table is None or not table.is_active:
        raise NotFoundException("Table not found or inactive.")

    # Check for existing active session at this table
    result = await db.execute(
        select(Session).where(
            Session.table_id == table_id,
            Session.status.in_(
                [SessionStatus.CREATED, SessionStatus.ACTIVE, SessionStatus.LOCKED]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictException(
            "An active session already exists at this table.")

    # Resolve timeout from restaurant config or use defaults
    timeout_minutes = settings.DEFAULT_SESSION_TIMEOUT_MINUTES
    if table.restaurant and table.restaurant.config:
        timeout_minutes = table.restaurant.config.get(
            "session_timeout_minutes", timeout_minutes
        )

    now = datetime.now(timezone.utc)
    session = Session(
        table_id=table_id,
        host_user_id=user.id,
        status=SessionStatus.ACTIVE,
        allow_additions=True,
        started_at=now,
        expires_at=now + timedelta(minutes=timeout_minutes),
    )
    db.add(session)
    await db.flush()

    # Add the host as the first session member
    host_member = SessionMember(
        session_id=session.id,
        user_id=user.id,
        role=MemberRole.HOST,
        status=MemberStatus.APPROVED,
        joined_at=now,
    )
    db.add(host_member)
    await db.flush()

    return session


async def get_session(db: AsyncSession, session_id: UUID) -> Session:
    """Fetch a session by ID, raising NotFoundException if missing."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundException("Session not found.")
    return session


async def request_join(db: AsyncSession, session_id: UUID, user: User) -> SessionMember:
    """Request to join an existing session. Creates a PENDING membership."""
    session = await get_session(db, session_id)
    _check_session_active(session)

    # Check max guests
    max_guests = settings.DEFAULT_MAX_GUESTS_PER_SESSION
    approved_count = sum(
        1 for m in session.members if m.status == MemberStatus.APPROVED
    )
    if approved_count >= max_guests:
        raise BadRequestException("Session is full.")

    # Check if already a member
    existing = next(
        (m for m in session.members if m.user_id ==
         user.id and m.status != MemberStatus.LEFT),
        None,
    )
    if existing:
        if existing.status == MemberStatus.APPROVED:
            raise ConflictException("Already a member of this session.")
        if existing.status == MemberStatus.PENDING:
            raise ConflictException("Join request already pending.")
        if existing.status == MemberStatus.REJECTED:
            raise ForbiddenException("Your join request was rejected.")

    member = SessionMember(
        session_id=session_id,
        user_id=user.id,
        role=MemberRole.GUEST,
        status=MemberStatus.PENDING,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.flush()
    return member


async def handle_member_action(
    db: AsyncSession,
    session_id: UUID,
    member_id: UUID,
    action: str,
    host_user: User,
) -> SessionMember:
    """Approve or reject a pending join request. Only the Host can do this."""
    session = await get_session(db, session_id)
    _check_session_active(session)

    if session.host_user_id != host_user.id:
        raise ForbiddenException("Only the session host can manage members.")

    result = await db.execute(
        select(SessionMember).where(
            SessionMember.id == member_id,
            SessionMember.session_id == session_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotFoundException("Member not found in this session.")

    if member.status != MemberStatus.PENDING:
        raise BadRequestException(f"Member is already {member.status.value}.")

    if action == "approve":
        member.status = MemberStatus.APPROVED
    elif action == "reject":
        member.status = MemberStatus.REJECTED
    else:
        raise BadRequestException(f"Invalid action: {action}")

    await db.flush()
    return member


async def toggle_additions(
    db: AsyncSession,
    session_id: UUID,
    allow: bool,
    host_user: User,
) -> Session:
    """Toggle whether guests can add items. Host-only."""
    session = await get_session(db, session_id)
    _check_session_active(session)

    if session.host_user_id != host_user.id:
        raise ForbiddenException("Only the session host can toggle additions.")

    session.allow_additions = allow
    await db.flush()
    return session


async def update_session_status(
    db: AsyncSession,
    session_id: UUID,
    new_status: SessionStatus,
) -> Session:
    """Update session status. Used internally for state transitions."""
    session = await get_session(db, session_id)
    session.status = new_status
    if new_status in (SessionStatus.COMPLETED, SessionStatus.CLOSED):
        session.closed_at = datetime.now(timezone.utc)
    await db.flush()
    return session


async def reopen_session(
    db: AsyncSession,
    session_id: UUID,
    new_timeout_minutes: int | None = None,
) -> Session:
    """Reopen a timed-out session. Admin-only (enforced at router level)."""
    session = await get_session(db, session_id)

    if session.status != SessionStatus.TIMED_OUT:
        raise BadRequestException("Only timed-out sessions can be reopened.")

    timeout = new_timeout_minutes or settings.DEFAULT_SESSION_TIMEOUT_MINUTES
    now = datetime.now(timezone.utc)

    session.status = SessionStatus.ACTIVE
    session.expires_at = now + timedelta(minutes=timeout)
    session.closed_at = None
    await db.flush()
    return session


def _check_session_active(session: Session) -> None:
    """Raise if session is not in an active, modifiable state."""
    if session.status == SessionStatus.TIMED_OUT:
        raise SessionExpiredException()
    if session.status == SessionStatus.LOCKED:
        raise SessionLockedException()
    if session.status not in (SessionStatus.CREATED, SessionStatus.ACTIVE):
        raise BadRequestException(
            f"Session is {session.status.value} and cannot be modified.")
