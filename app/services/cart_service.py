"""
Cart service -- add, remove, update items in the session's shared cart.
Cart items are stored as OrderItems with a NULL order_id until order submission.
Alternatively, we use a separate CartItem concept backed by Redis or a DB table.

Implementation note: For simplicity and real-time sync, cart items are stored
in-memory via Redis during the active session, and persisted to OrderItems
only at order submission time. This avoids creating a separate DB table for
transient cart state.
"""

import json
from uuid import UUID, uuid4

import redis.asyncio as aioredis

from app.core.exceptions import (
    BadRequestException, ForbiddenException, NotFoundException,
)
from app.models.session import Session, SessionStatus
from app.models.user import User
from app.schemas.cart import CartItemResponse, CartResponse


# Redis key for a session's cart
def _cart_key(session_id: UUID) -> str:
    return f"cart:{session_id}"


async def get_cart(redis: aioredis.Redis, session_id: UUID) -> CartResponse:
    """Retrieve the full cart for a session from Redis."""
    raw_items = await redis.hgetall(_cart_key(session_id))
    items = []
    total = 0.0
    for item_id, item_json in raw_items.items():
        item_data = json.loads(item_json)
        item = CartItemResponse(**item_data)
        items.append(item)
        total += item.menu_item_price * item.quantity

    return CartResponse(
        session_id=session_id,
        items=items,
        total=round(total, 2),
        item_count=len(items),
    )


async def add_item(
    redis: aioredis.Redis,
    session: Session,
    user: User,
    menu_item_id: UUID,
    menu_item_name: str,
    menu_item_price: float,
    quantity: int = 1,
    customizations: dict | None = None,
    notes: str | None = None,
) -> CartItemResponse:
    """Add an item to the session cart. Enforces session state and permissions."""
    _check_cart_modifiable(session, user)

    item_id = str(uuid4())
    item = CartItemResponse(
        id=item_id,
        menu_item_id=menu_item_id,
        menu_item_name=menu_item_name,
        menu_item_price=menu_item_price,
        added_by_id=user.id,
        added_by_name=user.display_name,
        quantity=quantity,
        customizations=customizations,
        notes=notes,
    )

    await redis.hset(_cart_key(session.id), item_id, item.model_dump_json())
    return item


async def update_item(
    redis: aioredis.Redis,
    session: Session,
    user: User,
    cart_item_id: str,
    quantity: int | None = None,
    customizations: dict | None = None,
    notes: str | None = None,
) -> CartItemResponse:
    """Update a cart item's quantity or customizations."""
    _check_cart_modifiable(session, user)

    raw = await redis.hget(_cart_key(session.id), cart_item_id)
    if raw is None:
        raise NotFoundException("Cart item not found.")

    item_data = json.loads(raw)
    item = CartItemResponse(**item_data)

    # Only the item's owner or the host can modify it
    if str(item.added_by_id) != str(user.id) and str(session.host_user_id) != str(user.id):
        raise ForbiddenException("You can only modify your own items.")

    if quantity is not None:
        item.quantity = quantity
    if customizations is not None:
        item.customizations = customizations
    if notes is not None:
        item.notes = notes

    await redis.hset(_cart_key(session.id), cart_item_id, item.model_dump_json())
    return item


async def remove_item(
    redis: aioredis.Redis,
    session: Session,
    user: User,
    cart_item_id: str,
) -> None:
    """Remove an item from the cart."""
    _check_cart_modifiable(session, user)

    raw = await redis.hget(_cart_key(session.id), cart_item_id)
    if raw is None:
        raise NotFoundException("Cart item not found.")

    item_data = json.loads(raw)

    # Guests can only remove their own; host can remove any
    if str(item_data["added_by_id"]) != str(user.id) and str(session.host_user_id) != str(user.id):
        raise ForbiddenException("You can only remove your own items.")

    await redis.hdel(_cart_key(session.id), cart_item_id)


async def clear_cart(redis: aioredis.Redis, session_id: UUID) -> None:
    """Remove all items from a session's cart. Called after order submission."""
    await redis.delete(_cart_key(session_id))


def _check_cart_modifiable(session: Session, user: User) -> None:
    """Ensure the session allows cart modifications for this user."""
    if session.status not in (SessionStatus.CREATED, SessionStatus.ACTIVE, SessionStatus.SUBMITTED, SessionStatus.IN_PROGRESS):
        raise BadRequestException(
            f"Cart is not modifiable in {session.status.value} state.")

    # If the user is not the host, check if additions are allowed
    if str(session.host_user_id) != str(user.id) and not session.allow_additions:
        raise ForbiddenException("The host has disabled item additions.")
