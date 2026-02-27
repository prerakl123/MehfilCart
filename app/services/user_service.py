"""
User service -- profile retrieval, display name updates, and name change requests.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.permissions import Role
from app.models.name_change_request import NameChangeRequest, NameChangeStatus
from app.models.restaurant import UserRole
from app.models.user import User


async def get_user_profile(db: AsyncSession, user: User) -> dict:
    """Build profile dict with resolved role and restaurant_id."""
    role, restaurant_id = await _resolve_role(db, user)
    return {
        "id": user.id,
        "phone": user.phone,
        "display_name": user.display_name,
        "role": role,
        "restaurant_id": restaurant_id,
    }


async def update_display_name(db: AsyncSession, user: User, new_name: str) -> dict:
    """
    Update display name directly for non-waiter users.
    For waiters, create a NameChangeRequest instead.
    """
    role, restaurant_id = await _resolve_role(db, user)

    if role == Role.WAITER:
        return await create_name_change_request(db, user, restaurant_id, new_name)

    # Direct update for admins, guests, hosts
    user.display_name = new_name
    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "phone": user.phone,
        "display_name": user.display_name,
        "role": role,
        "restaurant_id": restaurant_id,
        "pending_request": False,
    }


async def create_name_change_request(
    db: AsyncSession, user: User, restaurant_id: UUID, requested_name: str
) -> dict:
    """Create a pending name change request for staff approval."""
    # Check for existing pending request
    result = await db.execute(
        select(NameChangeRequest).where(
            NameChangeRequest.user_id == user.id,
            NameChangeRequest.status == NameChangeStatus.PENDING,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Update the existing pending request
        existing.requested_name = requested_name
        await db.commit()
        await db.refresh(existing)
    else:
        req = NameChangeRequest(
            user_id=user.id,
            restaurant_id=restaurant_id,
            requested_name=requested_name,
        )
        db.add(req)
        await db.commit()

    # TODO: Send notification to restaurant admin (email/push) when implemented
    print(f"[NAME_CHANGE_REQUEST] User {user.phone} requested name change to '{requested_name}'")

    role, _ = await _resolve_role(db, user)
    return {
        "id": user.id,
        "phone": user.phone,
        "display_name": user.display_name,
        "role": role,
        "restaurant_id": restaurant_id,
        "pending_request": True,
        "message": "Name change request submitted for admin approval.",
    }


async def list_name_change_requests(db: AsyncSession, restaurant_id: UUID) -> list:
    """List all pending name change requests for a restaurant."""
    result = await db.execute(
        select(NameChangeRequest)
        .where(
            NameChangeRequest.restaurant_id == restaurant_id,
            NameChangeRequest.status == NameChangeStatus.PENDING,
        )
        .order_by(NameChangeRequest.created_at.desc())
    )
    requests = result.scalars().all()

    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "restaurant_id": r.restaurant_id,
            "requested_name": r.requested_name,
            "status": r.status.value,
            "user_phone": r.user.phone if r.user else None,
            "current_name": r.user.display_name if r.user else None,
            "created_at": r.created_at,
        }
        for r in requests
    ]


async def handle_name_change_request(
    db: AsyncSession, request_id: UUID, action: str
) -> dict:
    """Approve or reject a name change request."""
    result = await db.execute(
        select(NameChangeRequest).where(NameChangeRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise NotFoundException("Name change request not found.")

    if req.status != NameChangeStatus.PENDING:
        raise BadRequestException("Request has already been processed.")

    if action == "approve":
        req.status = NameChangeStatus.APPROVED
        # Update the user's display name
        user_result = await db.execute(select(User).where(User.id == req.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.display_name = req.requested_name
        # TODO: Notify user of approval (email/push)
        print(
            f"[NAME_CHANGE_APPROVED] User {req.user_id} -> '{req.requested_name}'")
    elif action == "reject":
        req.status = NameChangeStatus.REJECTED
        # TODO: Notify user of rejection (email/push)
        print(
            f"[NAME_CHANGE_REJECTED] User {req.user_id} request for '{req.requested_name}'")
    else:
        raise BadRequestException("Action must be 'approve' or 'reject'.")

    await db.commit()
    await db.refresh(req)

    return {
        "id": req.id,
        "user_id": req.user_id,
        "restaurant_id": req.restaurant_id,
        "requested_name": req.requested_name,
        "status": req.status.value,
        "created_at": req.created_at,
    }


async def _resolve_role(db: AsyncSession, user: User) -> tuple[str, UUID | None]:
    """Resolve the user's primary role and associated restaurant."""
    SENTINEL_ID = "00000000-0000-0000-0000-000000000000"
    result = await db.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    user_roles = result.scalars().all()

    if not user_roles:
        return Role.TABLE_GUEST, None

    priority = [Role.SUPER_ADMIN, Role.RESTAURANT_ADMIN, Role.WAITER]
    for r in priority:
        matching = [ur for ur in user_roles if ur.role == r]
        if matching:
            rid = matching[0].restaurant_id
            if r == Role.SUPER_ADMIN or str(rid) == SENTINEL_ID:
                return r, None
            return r, rid

    return Role.TABLE_GUEST, None
