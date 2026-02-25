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
    session = await session_service.get_session(db, session_id)
    await cart_service.remove_item(redis, session, current_user, item_id)

    # Broadcast updated cart to the session
    updated_cart = await cart_service.get_cart(redis, session_id)
    await ws_manager.broadcast_to_room(
        f"session:{session_id}", "cart:updated", updated_cart.model_dump()
    )

    return MessageResponse(message="Item removed from cart.")
