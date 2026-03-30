"""Cart router -- add, update, remove items in a session's shared cart."""

from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartItemResponse, CartResponse
from app.services import cart_service, session_service, menu_service
from app.websocket.manager import ws_manager

router = APIRouter(prefix="/sessions/{session_id}/cart", tags=["Cart"])


@router.get(
    "",
    response_model=CartResponse,
    summary="Get Cart",
    description="Retrieve the current cart for a session.",
)
async def get_cart(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Retrieve the current shared cart for a session from Redis.

    :param session_id: UUID of the target session.
    :returns: CartResponse containing all items, total price, and item count.
    """
    return await cart_service.get_cart(redis, session_id)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=201,
    summary="Add Cart Item",
    description="Add a menu item to the session cart.",
)
async def add_cart_item(
    session_id: UUID,
    body: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Add a menu item to the session's shared cart and broadcast the updated cart via WebSocket.

    :param session_id: UUID of the target session.
    :param body: Cart item payload with menu_item_id, quantity, and optional customizations.
    :returns: The newly created CartItemResponse attributed to the current user.
    :raises BadRequestException: If the session state does not allow modifications.
    :raises ForbiddenException: If the host has disabled guest additions.
    """
    session = await session_service.get_session(db, session_id)
    menu_item = await menu_service.get_menu_item(db, body.menu_item_id)

    result = await cart_service.add_item(
        redis=redis,
        session=session,
        user=current_user,
        menu_item_id=menu_item.id,
        menu_item_name=menu_item.name,
        menu_item_price=float(menu_item.price),
        quantity=body.quantity,
        customizations=body.customizations,
        notes=body.notes,
    )

    # Broadcast updated cart to the session
    updated_cart = await cart_service.get_cart(redis, session_id)
    await ws_manager.broadcast_to_room(
        f"session:{session_id}", "cart:updated", updated_cart.model_dump()
    )

    return result


@router.patch(
    "/items/{item_id}",
    response_model=CartItemResponse,
    summary="Update Cart Item",
    description="Update quantity or customizations of a cart item.",
)
async def update_cart_item(
    session_id: UUID,
    item_id: str,
    body: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Update the quantity or customizations of an existing cart item and broadcast the change.
    Only the item's owner or the session host may update it.

    :param session_id: UUID of the session that owns the cart.
    :param item_id: String key of the cart item to update (Redis hash field).
    :param body: Fields to update; only provided fields are applied.
    :returns: Updated CartItemResponse.
    :raises NotFoundException: If the cart item does not exist.
    :raises ForbiddenException: If the current user is not allowed to modify this item.
    """
    session = await session_service.get_session(db, session_id)
    result = await cart_service.update_item(
        redis=redis,
        session=session,
        user=current_user,
        cart_item_id=item_id,
        quantity=body.quantity,
        customizations=body.customizations,
        notes=body.notes,
    )

    # Broadcast updated cart to the session
    updated_cart = await cart_service.get_cart(redis, session_id)
    await ws_manager.broadcast_to_room(
        f"session:{session_id}", "cart:updated", updated_cart.model_dump()
    )

    return result


@router.delete(
    "/items/{item_id}",
    response_model=MessageResponse,
    summary="Remove Cart Item",
    description="Remove an item from the session cart.",
)
async def remove_cart_item(
    session_id: UUID,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Remove an item from the session cart and broadcast the updated cart state.
    Guests may only remove their own items; the host can remove any item.

    :param session_id: UUID of the session that owns the cart.
    :param item_id: String key of the cart item to remove (Redis hash field).
    :returns: Confirmation message.
    :raises NotFoundException: If the cart item does not exist.
    :raises ForbiddenException: If the current user is not allowed to remove this item.
    """
    session = await session_service.get_session(db, session_id)
    await cart_service.remove_item(redis, session, current_user, item_id)

    # Broadcast updated cart to the session
    updated_cart = await cart_service.get_cart(redis, session_id)
    await ws_manager.broadcast_to_room(
        f"session:{session_id}", "cart:updated", updated_cart.model_dump()
    )

    return MessageResponse(message="Item removed from cart.")
