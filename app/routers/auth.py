"""Auth router -- OTP request, verification, token refresh, logout."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import UnauthorizedException
from app.core.redis import get_redis
from app.core.security import verify_refresh_token
from app.models.user import User
from app.schemas.auth import MessageResponse, OTPRequest, OTPVerify, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/request-otp",
    response_model=MessageResponse,
    summary="Request OTP",
    description="Send a 6-digit OTP to the provided phone number.",
)
async def request_otp(
    body: OTPRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Send a 6-digit OTP to the given phone number.
    Enforces rate-limiting and normalizes the number before dispatch.

    :param body: Request body containing the target phone number.
    :returns: Confirmation message with the masked phone number.
    :raises BadRequestException: If the phone number format is invalid.
    :raises RateLimitException: If too many OTP requests have been made recently.
    """
    message = await auth_service.request_otp(db, redis, body.phone)
    return MessageResponse(message=message)


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    summary="Verify OTP",
    description="Verify the OTP and receive JWT access and refresh tokens.",
)
async def verify_otp(
    body: OTPVerify,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Verify the OTP for a phone number and issue JWT access and refresh tokens.
    The refresh token is returned as an HttpOnly cookie.

    :param body: Request body with phone and OTP.
    :param response: FastAPI response object used to set the refresh token cookie.
    :returns: Access token, user info, and assigned role.
    :raises BadRequestException: If the OTP is invalid or expired.
    """
    token_response, refresh_token = await auth_service.verify_otp_and_authenticate(
        db, redis, body.phone, body.otp
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400
    )
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Exchange a valid refresh token cookie for a new access token.",
)
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Exchange a valid refresh token cookie for a new short-lived access token.

    :param request: Incoming request whose cookies are inspected for the refresh token.
    :returns: New access token and updated user information.
    :raises UnauthorizedException: If the refresh token cookie is absent or invalid.
    """
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        raise UnauthorizedException("Refresh token required.")

    payload = verify_refresh_token(refresh)
    return await auth_service.refresh_access_token(
        db, redis, payload["sub"], payload.get("role", ""),
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
    description="Invalidate the current refresh token.",
)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Invalidate the current user's refresh token and clear the browser cookie.

    :param response: FastAPI response object used to clear the refresh token cookie.
    :param current_user: The authenticated user derived from the access token.
    :returns: Confirmation message.
    """
    await auth_service.logout_user(redis, str(current_user.id))
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )
    return MessageResponse(message="Logged out successfully.")
