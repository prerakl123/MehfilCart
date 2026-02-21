"""
Custom exception classes for structured error handling.
All exceptions are caught by global handlers registered in app/__init__.py.
"""


class MehfilCartException(Exception):
    """Base exception for all application-level errors."""

    def __init__(self, detail: str = "An error occurred", status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundException(MehfilCartException):
    """Resource not found (404)."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=404)


class BadRequestException(MehfilCartException):
    """Invalid request data (400)."""

    def __init__(self, detail: str = "Bad request"):
        super().__init__(detail=detail, status_code=400)


class UnauthorizedException(MehfilCartException):
    """Authentication required or failed (401)."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(detail=detail, status_code=401)


class ForbiddenException(MehfilCartException):
    """Insufficient permissions (403)."""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(detail=detail, status_code=403)


class ConflictException(MehfilCartException):
    """Resource conflict (409)."""

    def __init__(self, detail: str = "Conflict"):
        super().__init__(detail=detail, status_code=409)


class RateLimitException(MehfilCartException):
    """Rate limit exceeded (429)."""

    def __init__(self, detail: str = "Rate limit exceeded. Please try again later."):
        super().__init__(detail=detail, status_code=429)


class SessionExpiredException(ForbiddenException):
    """Ordering session has timed out."""

    def __init__(self, detail: str = "Session has expired"):
        super().__init__(detail=detail)


class SessionLockedException(ForbiddenException):
    """Session is locked; no modifications allowed."""

    def __init__(self, detail: str = "Session is locked"):
        super().__init__(detail=detail)
