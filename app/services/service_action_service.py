"""Service action business logic."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundException, ForbiddenException
from app.models.service_action import ServiceAction, ActionStatus, ActionType
from app.models.session import Session, SessionStatus, SessionMember
from app.models.session_event import SessionEventType
from app.models.user import User
from app.services import session_event_service
from app.websocket.manager import ws_manager


async def create_service_action(
    db: AsyncSession, session_id: UUID, user: User, action_type: ActionType
) -> ServiceAction:
    """Create a new service action from a session member."""
    # Verify session is active and user is a member
    stmt = select(Session).where(Session.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session or session.status != SessionStatus.ACTIVE:
        raise NotFoundException("Active session not found")

    member_stmt = select(SessionMember).where(
        SessionMember.session_id == session_id,
        SessionMember.user_id == user.id
    )
    member_result = await db.execute(member_stmt)
    member = member_result.scalar_one_or_none()

    if not member:
        raise ForbiddenException("Only session members can request service")

    action = ServiceAction(
        session_id=session.id,
        restaurant_id=session.table.restaurant_id, # Requires table eager loading or lazy access (assuming lazy works here)
        table_id=session.table_id,
        action_type=action_type,
        requested_by_id=user.id,
    )
    db.add(action)
    await db.flush()

    await session_event_service.log_event(
        db, session_id, SessionEventType.SERVICE_ACTION_REQUESTED, actor_id=user.id,
        payload={"action_id": str(action.id), "action_type": action_type.value},
    )

    await db.commit()
    await db.refresh(action)

    # Broadcast to staff room
    staff_room = f"staff:{session.table.restaurant_id}"
    await ws_manager.broadcast_to_room(
        staff_room,
        "service_action:created",
        {"action_id": str(action.id), "table_label": session.table.label, "action_type": str(action.action_type)},
    )
    
    # Broadcast to session to acknowledge
    session_room = f"session:{session_id}"
    await ws_manager.broadcast_to_room(
        session_room,
        "service_action:created",
        {"action_id": str(action.id), "action_type": str(action.action_type)},
    )

    return action


async def get_pending_actions(db: AsyncSession, restaurant_id: UUID) -> list[ServiceAction]:
    """Get all pending or claimed service actions for a restaurant."""
    stmt = (
        select(ServiceAction)
        .where(
            ServiceAction.restaurant_id == restaurant_id,
            ServiceAction.status.in_([ActionStatus.PENDING, ActionStatus.CLAIMED])
        )
        .order_by(ServiceAction.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def claim_service_action(db: AsyncSession, action_id: UUID, user: User) -> ServiceAction:
    """Staff claims a service action."""
    stmt = select(ServiceAction).where(ServiceAction.id == action_id)
    result = await db.execute(stmt)
    action = result.scalar_one_or_none()

    if not action:
        raise NotFoundException("Service action not found")

    if action.status != ActionStatus.PENDING:
        raise ForbiddenException("Action is not pending")

    action.status = ActionStatus.CLAIMED
    action.claimed_by_id = user.id
    action.claimed_at = datetime.utcnow()
    await db.flush()

    await session_event_service.log_event(
        db, action.session_id, SessionEventType.SERVICE_ACTION_CLAIMED, actor_id=user.id,
        payload={"action_id": str(action.id), "action_type": action.action_type.value},
    )

    await db.commit()
    await db.refresh(action)

    # Notify staff
    staff_room = f"staff:{action.restaurant_id}"
    await ws_manager.broadcast_to_room(
        staff_room,
        "service_action:updated",
        {"action_id": str(action.id), "status": "CLAIMED"},
    )
    return action


async def complete_service_action(db: AsyncSession, action_id: UUID, user: User) -> ServiceAction:
    """Staff marks a service action as completed."""
    stmt = select(ServiceAction).where(ServiceAction.id == action_id)
    result = await db.execute(stmt)
    action = result.scalar_one_or_none()

    if not action:
        raise NotFoundException("Service action not found")

    # Either pending or claimed
    if action.status == ActionStatus.COMPLETED:
        raise ForbiddenException("Action already completed")

    action.status = ActionStatus.COMPLETED
    if not action.claimed_by_id:
        action.claimed_by_id = user.id
    action.completed_at = datetime.utcnow()
    await db.flush()

    await session_event_service.log_event(
        db, action.session_id, SessionEventType.SERVICE_ACTION_COMPLETED, actor_id=user.id,
        payload={"action_id": str(action.id), "action_type": action.action_type.value},
    )

    await db.commit()
    await db.refresh(action)

    staff_room = f"staff:{action.restaurant_id}"
    await ws_manager.broadcast_to_room(
        staff_room,
        "service_action:updated",
        {"action_id": str(action.id), "status": "COMPLETED"},
    )
    
    return action
