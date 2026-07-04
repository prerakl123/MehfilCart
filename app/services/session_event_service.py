"""Session event service -- append-only audit log for a session's timeline."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session_event import SessionEvent, SessionEventType


async def log_event(
    db: AsyncSession,
    session_id: UUID,
    event_type: SessionEventType,
    actor_id: UUID | None = None,
    payload: dict | None = None,
) -> SessionEvent:
    """
    Record one entry in a session's audit timeline.

    Callers are expected to have already validated the underlying action; this
    only appends the record. Does not commit -- relies on the caller's existing
    transaction (mirrors the flush-not-commit convention used elsewhere in the
    session/order services).
    """
    event = SessionEvent(
        session_id=session_id,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload or {},
    )
    db.add(event)
    await db.flush()
    return event


async def list_events(db: AsyncSession, session_id: UUID) -> list[SessionEvent]:
    """Fetch a session's full audit timeline in chronological order."""
    result = await db.execute(
        select(SessionEvent)
        .options(selectinload(SessionEvent.actor))
        .where(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.created_at.asc())
    )
    return list(result.scalars().all())
