"""Session router -- create, get, update, join, manage members, reopen."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.session import (
    MemberActionRequest, SessionCreate, SessionReopenRequest,
    SessionResponse, SessionUpdate, TransferHostRequest,
)
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    summary="Create Session",
    description="Create a new ordering session at a table. Caller becomes the Host.",
)
async def create_session(
    body: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.create_session(db, current_user, body.table_id)
    return session


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get Session",
    description="Retrieve details of a specific session.",
)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.get_session(db, session_id)


@router.get(
    "/table/{table_id}/active",
    response_model=SessionResponse,
    summary="Get Active Session for Table",
    description="Retrieve the active session for a table, if any.",
)
async def get_active_session_for_table(
    table_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.get_active_session_for_table(db, table_id)
    if not session:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("No active session found for this table.")
    return session


@router.get(
    "/my/active",
    response_model=SessionResponse,
    summary="Get My Active Session",
    description="Retrieve the active session for the current authenticated user, if any.",
)
async def get_my_active_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.get_my_active_session(db, current_user)
    if not session:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("You do not have an active session.")
    return session


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update Session",
    description="Lock session or toggle item additions (Host only).",
)
async def update_session(
    session_id: UUID,
    body: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await session_service.get_session(db, session_id)
    if body.allow_additions is not None:
        session = await session_service.toggle_additions(
            db, session_id, body.allow_additions, current_user,
        )
    if body.status is not None:
        session = await session_service.update_session_status(db, session_id, body.status)
    return session


@router.post(
    "/{session_id}/join",
    response_model=MessageResponse,
    summary="Join Session",
    description="Request to join an existing session at a table.",
)
async def join_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await session_service.request_join(db, session_id, current_user)
    return MessageResponse(message="Join request sent. Waiting for host approval.")


@router.patch(
    "/{session_id}/members/{member_id}",
    response_model=MessageResponse,
    summary="Approve/Reject Member",
    description="Host approves or rejects a pending join request.",
)
async def handle_member(
    session_id: UUID,
    member_id: UUID,
    body: MemberActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await session_service.handle_member_action(
        db, session_id, member_id, body.action, current_user,
    )
    return MessageResponse(message=f"Member {body.action}d successfully.")


@router.post(
    "/{session_id}/reopen",
    response_model=SessionResponse,
    summary="Reopen Session",
    description="Reopen a timed-out session (Admin only).",
)
async def reopen_session(
    session_id: UUID,
    body: SessionReopenRequest,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("session:manage")),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.reopen_session(db, session_id, body.new_timeout_minutes)


@router.post(
    "/{session_id}/leave",
    response_model=MessageResponse,
    summary="Leave Session",
    description="Leave an active session. If you are the host, this ends the session for all.",
)
async def leave_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await session_service.leave_session(db, session_id, current_user)
    return MessageResponse(message="Successfully left the session.")


@router.post(
    "/{session_id}/transfer-host",
    response_model=SessionResponse,
    summary="Transfer Host",
    description="Transfer the hosting duty to another member.",
)
async def transfer_host(
    session_id: UUID,
    body: TransferHostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.transfer_host(db, session_id, body.new_host_id, current_user)


@router.delete(
    "/{session_id}",
    response_model=MessageResponse,
    summary="Close Session",
    description="Close/end an active session.",
)
async def close_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.session import SessionStatus
    await session_service.update_session_status(db, session_id, SessionStatus.CLOSED)
    return MessageResponse(message="Session closed.")
