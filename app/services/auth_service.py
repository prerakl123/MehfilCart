"""
Auth service -- OTP request, verification, user creation, and JWT issuance.
"""

from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.permissions import Role
from app.core.security import create_access_token, create_refresh_token
from app.models.restaurant import UserRole
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.utils.otp import check_rate_limit, generate_otp, send_otp, store_otp, verify_otp
from app.utils.phone import is_valid_phone, normalize_phone


async def request_otp(db: AsyncSession, redis: aioredis.Redis, phone: str) -> str:
    """
    Generate and send an OTP to the given phone number.
    Returns a confirmation message.
    """
    phone = normalize_phone(phone)
    if not is_valid_phone(phone):
        raise BadRequestException("Invalid phone number format.")

    await check_rate_limit(redis, phone)

    otp = generate_otp()
    await store_otp(redis, phone, otp)
    await send_otp(phone, otp)

    return f"OTP sent to {phone[-4:].rjust(len(phone), '*')}"


async def verify_otp_and_authenticate(
    db: AsyncSession,
    redis: aioredis.Redis,
    phone: str,
    otp: str,
) -> TokenResponse:
    """
    Verify OTP, create or fetch user, and issue JWT tokens.
    Returns tokens and user info.
    """
    phone = normalize_phone(phone)
    await verify_otp(redis, phone, otp)

    # Fetch or create user
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(phone=phone, display_name=None)
        db.add(user)
        await db.flush()

    user.last_login_at = datetime.now(timezone.utc)

    # Determine the user's primary role and associated restaurant
    role, restaurant_id = await _resolve_user_role(db, user)

    access_token = create_access_token(user.id, role)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token in Redis for validation/blacklisting
    await redis.setex(
        f"refresh_token:{user.id}",
        settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400,
        refresh_token,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        display_name=user.display_name,
        role=role,
        restaurant_id=str(restaurant_id) if restaurant_id else None,
    )


async def refresh_access_token(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    role: str,
) -> TokenResponse:
    """Issue a new access token for a validated refresh token."""
    from uuid import UUID
    uid = UUID(user_id)

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise BadRequestException("User not found")

    # Re-resolve role in case it changed
    current_role, restaurant_id = await _resolve_user_role(db, user)

    access_token = create_access_token(user.id, current_role)
    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        display_name=user.display_name,
        role=current_role,
        restaurant_id=str(restaurant_id) if restaurant_id else None,
    )


async def logout_user(redis: aioredis.Redis, user_id: str) -> None:
    """Invalidate the refresh token for a user."""
    await redis.delete(f"refresh_token:{user_id}")


async def _resolve_user_role(db: AsyncSession, user: User) -> tuple[str, str | None]:
    """
    Determine the user's highest-privilege role and associated restaurant_id.
    Returns (role, restaurant_id). SUPER_ADMIN gets None for restaurant_id.
    Falls back to (TABLE_GUEST, None) if no explicit role is assigned.
    """
    SENTINEL_ID = "00000000-0000-0000-0000-000000000000"

    result = await db.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    user_roles = result.scalars().all()

    if not user_roles:
        return Role.TABLE_GUEST, None

    # Priority order for role resolution
    priority = [Role.SUPER_ADMIN, Role.RESTAURANT_ADMIN, Role.WAITER]
    for r in priority:
        matching = [ur for ur in user_roles if ur.role == r]
        if matching:
            rid = matching[0].restaurant_id
            # SUPER_ADMIN uses the sentinel restaurant -- return None
            if r == Role.SUPER_ADMIN or str(rid) == SENTINEL_ID:
                return r, None
            return r, rid

    return Role.TABLE_GUEST, None
