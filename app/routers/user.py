"""User router -- profile retrieval and display name management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserProfileUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get My Profile",
    description="Retrieve the current authenticated user's profile.",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the profile of the currently authenticated user including their role and restaurant.

    :param current_user: User resolved from the Bearer token.
    :returns: Profile data including id, phone, display name, role, and restaurant id.
    """
    return await user_service.get_user_profile(db, current_user)


@router.patch(
    "/me",
    summary="Update My Profile",
    description="Update display name. Staff changes require admin approval.",
)
async def update_my_profile(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the current user's display name.
    Waiter-role users have their request queued for admin approval instead of being applied directly.

    :param body: Request body containing the desired new display name.
    :returns: Updated profile dict; includes a ``pending_request`` flag for waiters.
    """
    return await user_service.update_display_name(db, current_user, body.display_name)
