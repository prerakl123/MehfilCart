"""OTP generation, storage, and verification utilities."""

import random
import string

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.exceptions import BadRequestException, RateLimitException


def generate_otp(length: int = None) -> str:
    """Generate a random numeric OTP of configured length."""
    length = length or settings.OTP_LENGTH
    return "".join(random.choices(string.digits, k=length))


def _otp_key(phone: str) -> str:
    """Redis key for storing an OTP against a phone number."""
    return f"otp:{phone}"


def _otp_attempts_key(phone: str) -> str:
    """Redis key for tracking OTP verification attempts."""
    return f"otp_attempts:{phone}"


def _rate_limit_key(phone: str) -> str:
    """Redis key for tracking OTP request rate limiting."""
    return f"otp_rate:{phone}"


async def check_rate_limit(redis: aioredis.Redis, phone: str) -> None:
    """Ensure the phone number hasn't exceeded OTP request limits."""
    key = _rate_limit_key(phone)
    count = await redis.get(key)
    if count and int(count) >= settings.OTP_RATE_LIMIT_MAX:
        raise RateLimitException(
            f"Too many OTP requests. Try again after {settings.OTP_RATE_LIMIT_WINDOW_MINUTES} minutes."
        )


async def store_otp(redis: aioredis.Redis, phone: str, otp: str) -> None:
    """Store OTP in Redis with TTL and increment rate limit counter."""
    # Store the OTP
    await redis.setex(_otp_key(phone), settings.OTP_EXPIRY_SECONDS, otp)
    # Reset attempts counter
    await redis.delete(_otp_attempts_key(phone))
    # Increment rate limit counter
    rate_key = _rate_limit_key(phone)
    pipe = redis.pipeline()
    pipe.incr(rate_key)
    pipe.expire(rate_key, settings.OTP_RATE_LIMIT_WINDOW_MINUTES * 60)
    await pipe.execute()


async def verify_otp(redis: aioredis.Redis, phone: str, otp: str) -> bool:
    """Verify OTP against Redis. Returns True on success, raises on failure."""
    # Check attempts
    attempts_key = _otp_attempts_key(phone)
    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= settings.OTP_MAX_ATTEMPTS:
        raise BadRequestException(
            "Too many failed attempts. Request a new OTP.")

    stored_otp = await redis.get(_otp_key(phone))
    if stored_otp is None:
        raise BadRequestException(
            "OTP expired or not found. Request a new one.")

    if stored_otp != otp:
        # Increment failed attempts
        pipe = redis.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, settings.OTP_EXPIRY_SECONDS)
        await pipe.execute()
        raise BadRequestException("Invalid OTP.")

    # Success: clean up
    await redis.delete(_otp_key(phone), attempts_key)
    return True


async def send_otp(phone: str, otp: str) -> None:
    """
    Send OTP via SMS provider.
    In dev mode (provider="console"), prints to console.
    TODO: Implement MSG91 and Twilio integrations.
    """
    if settings.OTP_PROVIDER == "console":
        print(f"[DEV OTP] Phone: {phone} | OTP: {otp}")
    elif settings.OTP_PROVIDER == "msg91":
        # TODO: Implement MSG91 API call
        raise NotImplementedError("MSG91 OTP provider not yet implemented")
    elif settings.OTP_PROVIDER == "twilio":
        # TODO: Implement Twilio API call
        raise NotImplementedError("Twilio OTP provider not yet implemented")
    else:
        raise ValueError(f"Unknown OTP provider: {settings.OTP_PROVIDER}")
