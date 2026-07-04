"""
JWT creation, validation, and password utilities.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt import PyJWTError

from app.core.config import settings
from app.core.exceptions import UnauthorizedException


def create_access_token(user_id: UUID, role: str) -> str:
    """Create a short-lived JWT access token."""
    expires = datetime.now(
        timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expires,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    """Create a long-lived JWT refresh token."""
    expires = datetime.now(timezone.utc) + \
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expires,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises UnauthorizedException on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=[settings.JWT_ALGORITHM])
        if payload.get("sub") is None:
            raise UnauthorizedException("Invalid token: missing subject")
        return payload
    except PyJWTError as e:
        raise UnauthorizedException(f"Invalid or expired token: {e}")


def verify_access_token(token: str) -> dict:
    """Decode an access token and ensure it is the correct type."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedException(
            "Invalid token type: expected access token")
    return payload


def verify_refresh_token(token: str) -> dict:
    """Decode a refresh token and ensure it is the correct type."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise UnauthorizedException(
            "Invalid token type: expected refresh token")
    return payload
