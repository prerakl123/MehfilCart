"""Auth schemas -- OTP request/verify and token responses."""

from pydantic import BaseModel, Field


class OTPRequest(BaseModel):
    """Request body to send an OTP to a phone number."""
    phone: str = Field(..., min_length=10, max_length=15,
                       examples=["+919876543210"])


class OTPVerify(BaseModel):
    """Request body to verify an OTP and obtain tokens."""
    phone: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    """Returned after successful OTP verification or token refresh."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str | None = None
    role: str | None = None
    restaurant_id: str | None = None
    profile_incomplete: bool = False


class RefreshRequest(BaseModel):
    """Request body for token refresh (refresh token sent via cookie or body)."""
    refresh_token: str | None = None


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
