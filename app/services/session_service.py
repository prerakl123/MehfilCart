"""
Session service -- create, join, manage members, timeout enforcement, reopen.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException, ConflictException, ForbiddenException,
    NotFoundException, SessionExpiredException, SessionLockedException,
)
from app.models.order import Order, OrderStatus
from app.models.session import (
    MemberRole, MemberStatus, Session, SessionMember, SessionStatus,
)
from app.models.session_event import SessionEventType
from app.models.table import Table
from app.models.user import User
from app.services import session_event_service


def _session_load_options():
    """Standard eager-load options for Session queries returned to the API."""
    return [
        selectinload(Session.members).selectinload(SessionMember.user),
        selectinload(Session.table),
    ]


async def create_session(db: AsyncSession, user: User, table_id: UUID) -> Session:
    """
    Create a new ordering session at a table. The user becomes the Host.
    Ensures no other active session exists at the same table.
    """
    # Verify table exists and is active
    result = await db.execute(
        select(Table).options(selectinload(Table.restaurant)).where(Table.id == table_id)
    )
    table = result.scalar_one_or_none()
    if table is None or not table.is_active:
        raise NotFoundException("Table not found or inactive.")

    # Check for existing active session at this table
    result = await db.execute(
        select(Session).where(
            Session.table_id == table_id,
            Session.status.in_(
                [SessionStatus.CREATED, SessionStatus.ACTIVE, SessionStatus.LOCKED,
                 SessionStatus.SUBMITTED, SessionStatus.IN_PROGRESS]),
        )
    )
    existing = result.scalars().first()
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

    await session_event_service.log_event(
        db, session.id, SessionEventType.SESSION_CREATED, actor_id=user.id,
        payload={"table_id": str(table_id)},
    )

    # Re-query with eager loads so the response serializer can access members
    result = await db.execute(
        select(Session).options(*_session_load_options()).where(Session.id == session.id)
    )
    return result.scalar_one()


async def get_session(db: AsyncSession, session_id: UUID) -> Session:
    """Fetch a session by ID, raising NotFoundException if missing."""
    result = await db.execute(
        select(Session).options(*_session_load_options()).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundException("Session not found.")
    return session


async def get_active_session_for_table(db: AsyncSession, table_id: UUID) -> Session | None:
    """Fetch the currently active session for a table, if any."""
    result = await db.execute(
        select(Session).options(*_session_load_options()).where(
            Session.table_id == table_id,
            Session.status.in_(
                [SessionStatus.CREATED, SessionStatus.ACTIVE, SessionStatus.LOCKED,
                 SessionStatus.SUBMITTED, SessionStatus.IN_PROGRESS])
        ).order_by(Session.started_at.desc())
    )
    return result.scalars().first()


async def get_my_active_session(db: AsyncSession, user: User) -> Session | None:
    """Fetch the currently active session for a specific user, if any."""
    result = await db.execute(
        select(Session)
        .join(SessionMember, Session.id == SessionMember.session_id)
        .options(*_session_load_options())
        .where(
            SessionMember.user_id == user.id,
            SessionMember.status == MemberStatus.APPROVED,
            Session.status.in_([SessionStatus.CREATED, SessionStatus.ACTIVE, SessionStatus.LOCKED,
                                SessionStatus.SUBMITTED, SessionStatus.IN_PROGRESS])
        ).order_by(Session.started_at.desc())
    )
    return result.scalars().first()


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

    await session_event_service.log_event(
        db, session_id, SessionEventType.MEMBER_JOIN_REQUESTED, actor_id=user.id,
        payload={"display_name": user.display_name},
    )
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
        event_type = SessionEventType.MEMBER_APPROVED
    elif action == "reject":
        member.status = MemberStatus.REJECTED
        event_type = SessionEventType.MEMBER_REJECTED
    else:
        raise BadRequestException(f"Invalid action: {action}")

    await db.flush()

    await session_event_service.log_event(
        db, session_id, event_type, actor_id=host_user.id,
        payload={"member_user_id": str(member.user_id)},
    )
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


async def _finalize_session_orders(db: AsyncSession, session_id: UUID) -> list[UUID]:
    """
    Transition a closing session's orders out of the live pipeline so they stop
    counting as "active" on staff/admin dashboards. SERVED orders are marked
    COMPLETED; anything still in RECEIVED/PREPARING/READY is CANCELLED, since the
    session ended before the kitchen finished them.

    :param session_id: UUID of the session being closed.
    :returns: IDs of the orders that were updated, for broadcasting by the caller.
    """
    result = await db.execute(
        select(Order).where(
            Order.session_id == session_id,
            Order.status.in_([
                OrderStatus.RECEIVED, OrderStatus.PREPARING,
                OrderStatus.READY, OrderStatus.SERVED,
            ]),
        )
    )
    orders = result.scalars().all()
    for order in orders:
        from_status = order.status
        if order.status == OrderStatus.SERVED:
            order.status = OrderStatus.COMPLETED
        else:
            order.status = OrderStatus.CANCELLED
            order.cancel_reason = "Session closed before the order was served."
        await session_event_service.log_event(
            db, session_id, SessionEventType.ORDER_STATUS_CHANGED,
            payload={
                "order_id": str(order.id),
                "from_status": from_status.value,
                "to_status": order.status.value,
                "reason": "Session closed",
            },
        )
    await db.flush()
    return [order.id for order in orders]


async def update_session_status(
    db: AsyncSession,
    session_id: UUID,
    new_status: SessionStatus,
    actor_id: UUID | None = None,
) -> tuple[Session, list[UUID]]:
    """
    Update session status. Used internally for state transitions.

    :returns: The updated session, and the IDs of any orders auto-finalized
        as a result of the session closing (empty unless closing).
    """
    session = await get_session(db, session_id)
    from_status = session.status
    session.status = new_status
    finalized_order_ids: list[UUID] = []
    if new_status in (SessionStatus.COMPLETED, SessionStatus.CLOSED):
        session.closed_at = datetime.now(timezone.utc)
        finalized_order_ids = await _finalize_session_orders(db, session_id)
        await session_event_service.log_event(
            db, session_id, SessionEventType.SESSION_CLOSED, actor_id=actor_id,
            payload={"from_status": from_status.value},
        )
    else:
        await session_event_service.log_event(
            db, session_id, SessionEventType.SESSION_STATUS_CHANGED, actor_id=actor_id,
            payload={"from_status": from_status.value, "to_status": new_status.value},
        )
    await db.flush()
    return session, finalized_order_ids


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


async def leave_session(db: AsyncSession, session_id: UUID, user: User) -> list[UUID]:
    """
    Leave the session. If the user is the host, close the session for everyone.

    :returns: IDs of any orders auto-finalized because the session closed
        (empty unless the leaving user was the host).
    """
    session = await get_session(db, session_id)
    if session.status in (SessionStatus.COMPLETED, SessionStatus.CLOSED, SessionStatus.TIMED_OUT):
        raise BadRequestException("The session is already closed or inactive.")

    if session.host_user_id == user.id:
        # Host leaves: session ends for all
        session.status = SessionStatus.CLOSED
        session.closed_at = datetime.now(timezone.utc)
        finalized_order_ids = await _finalize_session_orders(db, session_id)
        await session_event_service.log_event(
            db, session_id, SessionEventType.SESSION_CLOSED, actor_id=user.id,
            payload={"reason": "Host left the session."},
        )
        await db.flush()
        return finalized_order_ids

    # Guest leaves
    member = next((m for m in session.members if m.user_id == user.id and m.status in (MemberStatus.APPROVED, MemberStatus.PENDING)), None)
    if not member:
        raise NotFoundException("You are not an active member of this session.")

    member.status = MemberStatus.LEFT
    await db.flush()

    await session_event_service.log_event(
        db, session_id, SessionEventType.MEMBER_LEFT, actor_id=user.id,
    )
    return []


async def transfer_host(db: AsyncSession, session_id: UUID, new_host_id: UUID, host_user: User) -> Session:
    """Transfer the hosting duty to another member."""
    session = await get_session(db, session_id)
    _check_session_active(session)

    if session.host_user_id != host_user.id:
        raise ForbiddenException("Only the session host can transfer hosting duty.")

    new_host_member = next((m for m in session.members if m.user_id == new_host_id and m.status == MemberStatus.APPROVED), None)
    if not new_host_member:
        raise BadRequestException("The new host must be an approved member of the session.")

    # Prevent transferring to self
    if new_host_id == host_user.id:
        raise BadRequestException("You are already the host.")

    current_host_member = next((m for m in session.members if m.user_id == host_user.id and m.status == MemberStatus.APPROVED), None)

    # Transfer host
    session.host_user_id = new_host_id
    new_host_member.role = MemberRole.HOST
    if current_host_member:
        current_host_member.role = MemberRole.GUEST

    await db.flush()
    return session


def _check_session_active(session: Session) -> None:
    """Raise if session is not in an active, modifiable state."""
    if session.status == SessionStatus.TIMED_OUT:
        raise SessionExpiredException()
    if session.status == SessionStatus.LOCKED:
        raise SessionLockedException()
    if session.status not in (SessionStatus.CREATED, SessionStatus.ACTIVE, SessionStatus.SUBMITTED, SessionStatus.IN_PROGRESS):
        raise BadRequestException(
            f"Session is {session.status.value} and cannot be modified.")
