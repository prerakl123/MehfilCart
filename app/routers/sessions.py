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
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/sessions", tags=["Sessions"])

async def _broadcast_session_update(session_id: UUID, db: AsyncSession):
    """
    Re-fetch the session and push its latest state to all members via WebSocket.

    :param session_id: UUID of the session to broadcast.
    :param db: Active database session for the re-fetch query.
    """
    # Run in a separate scope to prevent transaction collisions? No, just run it before return.
    session = await session_service.get_session(db, session_id)
    payload = SessionResponse.model_validate(session).model_dump()
    await ws_manager.broadcast_to_room(f"session:{session_id}", "session:updated", payload)


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
    """
    Create a new collaborative ordering session at the specified table.
    The calling user automatically becomes the session Host.

    :param body: Request body containing the target table_id.
    :returns: Fully populated SessionResponse with the host listed as the first member.
    :raises NotFoundException: If the table does not exist or is inactive.
    :raises ConflictException: If an active session already exists at that table.
    """
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
    """
    Retrieve the full details of a session including its members and table info.

    :param session_id: UUID of the session to retrieve.
    :returns: SessionResponse with members, table label, and current status.
    :raises NotFoundException: If no session with the given ID exists.
    """
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
    """
    Retrieve the currently active session at a given table, if one exists.

    :param table_id: UUID of the table to look up.
    :returns: SessionResponse for the active session.
    :raises NotFoundException: If no active session is found at the table.
    """
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
    """
    Retrieve the active session the current user belongs to, if any.

    :param current_user: Authenticated user resolved from the Bearer token.
    :returns: SessionResponse for the user's active session.
    :raises NotFoundException: If the user has no active session membership.
    """
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
    """
    Update session properties such as the allow_additions flag or status. Host-only.
    Broadcasts the updated session state to all WebSocket room members.

    :param session_id: UUID of the session to update.
    :param body: Fields to update; only provided fields are applied.
    :returns: Updated SessionResponse.
    :raises ForbiddenException: If the current user is not the session host.
    """
    session = await session_service.get_session(db, session_id)
    if body.allow_additions is not None:
        session = await session_service.toggle_additions(
            db, session_id, body.allow_additions, current_user,
        )
    if body.status is not None:
        session = await session_service.update_session_status(db, session_id, body.status)
        
    await _broadcast_session_update(session_id, db)
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
    """
    Send a join request to an active session; creates a PENDING membership.
    The host must approve the request before the user can interact with the cart.

    :param session_id: UUID of the session to join.
    :returns: Confirmation message indicating the request is awaiting host approval.
    :raises ConflictException: If the user is already a member or has a pending request.
    :raises ForbiddenException: If the user's previous request was rejected.
    """
    await session_service.request_join(db, session_id, current_user)
    await _broadcast_session_update(session_id, db)
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
    """
    Approve or reject a pending join request. Restricted to the session host.
    Broadcasts the updated session state after the action.

    :param session_id: UUID of the session.
    :param member_id: UUID of the SessionMember record to act on.
    :param body: Action payload — either ``"approve"`` or ``"reject"``.
    :returns: Confirmation message with the applied action.
    :raises ForbiddenException: If the current user is not the session host.
    :raises NotFoundException: If the member record is not found in this session.
    """
    await session_service.handle_member_action(
        db, session_id, member_id, body.action, current_user,
    )
    await _broadcast_session_update(session_id, db)
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
    """
    Reopen a timed-out session and extend its expiry. Requires ``session:manage`` permission.

    :param session_id: UUID of the timed-out session to reopen.
    :param body: Optional new timeout in minutes; defaults to the platform setting.
    :returns: Updated SessionResponse with ACTIVE status and new expiry time.
    :raises BadRequestException: If the session is not in TIMED_OUT state.
    """
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
    """
    Leave an active session. If the leaving user is the host, the session is closed for everyone.

    :param session_id: UUID of the session to leave.
    :returns: Confirmation message.
    :raises BadRequestException: If the session is already closed or inactive.
    :raises NotFoundException: If the user has no active membership in the session.
    """
    await session_service.leave_session(db, session_id, current_user)
    await _broadcast_session_update(session_id, db)
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
    """
    Transfer the Host role to another approved member of the session.
    The current host becomes a regular Guest after the transfer.

    :param session_id: UUID of the active session.
    :param body: Request body with the ``new_host_id`` of the target member.
    :returns: Updated SessionResponse reflecting the new host.
    :raises ForbiddenException: If the current user is not the existing host.
    :raises BadRequestException: If the target member is not an approved session member.
    """
    session = await session_service.transfer_host(db, session_id, body.new_host_id, current_user)
    await _broadcast_session_update(session_id, db)
    return session


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
    """
    Permanently close an active session, transitioning it to CLOSED state.
    Broadcasts the final session state to all connected WebSocket members.

    :param session_id: UUID of the session to close.
    :returns: Confirmation message.
    """
    from app.models.session import SessionStatus
    await session_service.update_session_status(db, session_id, SessionStatus.CLOSED)
    await _broadcast_session_update(session_id, db)
    return MessageResponse(message="Session closed.")
