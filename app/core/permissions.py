"""
Role definitions and permission enforcement.
This is the authoritative permission source for the entire platform.
"""

from enum import StrEnum

from app.core.exceptions import ForbiddenException


class Role(StrEnum):
    """All user roles in the platform hierarchy."""
    SUPER_ADMIN = "SUPER_ADMIN"
    RESTAURANT_ADMIN = "RESTAURANT_ADMIN"
    WAITER = "WAITER"
    TABLE_HOST = "TABLE_HOST"
    TABLE_GUEST = "TABLE_GUEST"


# Authoritative permission matrix: role -> set of allowed action strings
ROLE_PERMISSIONS: dict[str, list[str]] = {
    Role.SUPER_ADMIN: ["*"],
    Role.RESTAURANT_ADMIN: [
        "menu:manage", "table:manage", "session:manage",
        "order:view", "order:cancel", "order:edit",
        "staff:manage", "config:manage",
    ],
    Role.WAITER: [
        "order:view", "order:cancel", "order:status-update",
    ],
    Role.TABLE_HOST: [
        "session:create", "session:manage-members",
        "cart:add", "cart:remove-any", "cart:toggle-additions",
        "order:submit", "order:view-own",
    ],
    Role.TABLE_GUEST: [
        "cart:add", "cart:remove-own", "order:view-own",
    ],
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms


def check_permission(role: str, permission: str) -> None:
    """Raise ForbiddenException if the role lacks the required permission."""
    if not has_permission(role, permission):
        raise ForbiddenException(
            f"Role '{role}' does not have permission '{permission}'"
        )
