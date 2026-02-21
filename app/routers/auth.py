"""Auth router -- OTP request, verification, token refresh, logout."""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

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
    token_response = await auth_service.verify_otp_and_authenticate(
        db, redis, body.phone, body.otp
    )
    # TODO: Set refresh token as httpOnly cookie
    # response.set_cookie(
    #     key="refresh_token", value=refresh_token,
    #     httponly=True, secure=True, samesite="lax",
    #     max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400,
    # )
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Exchange a valid refresh token for a new access token.",
)
async def refresh_token(
    body: dict,  # Expects { "refresh_token": "..." }
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    refresh = body.get("refresh_token")
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
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    await auth_service.logout_user(redis, str(current_user.id))
    return MessageResponse(message="Logged out successfully.")
