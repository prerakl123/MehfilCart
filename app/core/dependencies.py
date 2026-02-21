"""
FastAPI dependencies for request-level injection.
Provides: database session, current user, and permission-checking utilities.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.permissions import check_permission
from app.core.security import verify_access_token
from app.models.user import User

# Extracts Bearer token from the Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: decode the JWT from the Authorization header, load the user from DB.
    Raises UnauthorizedException if token is missing, invalid, or user not found.
    """
    if credentials is None:
        raise UnauthorizedException("Authorization header missing")

    payload = verify_access_token(credentials.credentials)
    user_id = UUID(payload["sub"])

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedException("User not found")
    if user.is_blocked:
        raise ForbiddenException("User account is blocked")

    # Attach the decoded role to the user object for downstream permission checks
    user._current_role = payload.get("role", "")
    return user


def require_permission(permission: str):
    """
    Returns a dependency that checks the current user's role against a permission.
    Usage: `_: None = Depends(require_permission("cart:add"))`
    """
    async def _check(current_user: User = Depends(get_current_user)):
        check_permission(current_user._current_role, permission)
    return _check


def require_any_role(*roles: str):
    """
    Returns a dependency that checks the current user has one of the specified roles.
    Usage: `_: None = Depends(require_any_role("SUPER_ADMIN", "RESTAURANT_ADMIN"))`
    """
    async def _check(current_user: User = Depends(get_current_user)):
        if current_user._current_role not in roles:
            raise ForbiddenException(
                f"Requires one of roles: {', '.join(roles)}"
            )
    return _check
