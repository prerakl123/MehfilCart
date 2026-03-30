"""Order router -- submit, list, get, status update, cancel."""

from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.redis import get_redis
from app.models.order import OrderStatus
from app.models.user import User
from app.schemas.order import (
    OrderCancelRequest, OrderResponse, OrderStatusUpdate, OrderSubmit,
)
from app.services import order_service, session_service
from app.websocket.manager import ws_manager
from app.schemas.cart import CartResponse

router = APIRouter(tags=["Orders"])


@router.post(
    "/sessions/{session_id}/orders",
    response_model=OrderResponse,
    status_code=201,
    summary="Submit Order",
    description="Submit the current cart as a finalized order (Host only).",
)
async def submit_order(
    session_id: UUID,
    body: OrderSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Convert the session's Redis cart into a persisted Order. Host-only operation.
    Broadcasts the cleared cart and the new order to all relevant WebSocket rooms.

    :param session_id: UUID of the session whose cart should be submitted.
    :param body: Optional special notes to attach to the order.
    :returns: The fully populated OrderResponse.
    :raises ForbiddenException: If the current user is not the session host.
    :raises BadRequestException: If the cart is empty or the session state forbids submission.
    """
    session = await session_service.get_session(db, session_id)
    order = await order_service.submit_order(
        db, redis, session, current_user, body.special_notes,
    )

    # Broadcast empty cart to all session members so their UIs clear
    empty_cart = CartResponse(session_id=session_id, items=[], total=0, item_count=0)
    await ws_manager.broadcast_to_room(
        f"session:{session_id}", "cart:updated", empty_cart.model_dump()
    )

    # Broadcast new order to staff, admin, and session members
    try:
        order_dict = OrderResponse.model_validate(order).model_dump(mode="json")
        restaurant_id = order.session.table.restaurant_id
        await ws_manager.broadcast_to_room(f"admin:{restaurant_id}", "order:created", order_dict)
        await ws_manager.broadcast_to_room(f"staff:{restaurant_id}", "order:created", order_dict)
        await ws_manager.broadcast_to_room(f"session:{session_id}", "order:created", order_dict)
    except Exception as e:
        print("Error broadcasting order: ", e)

    return order


@router.get(
    "/orders",
    summary="List Orders",
    description="List orders, with optional filters. Filtered by role access.",
)
async def list_orders(
    session_id: UUID | None = Query(default=None),
    status: OrderStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List orders with optional filters for session and status, supporting pagination.

    :param session_id: If provided, restrict results to this session's orders.
    :param status: If provided, restrict results to orders with this status.
    :param limit: Maximum number of orders to return (1–100).
    :param offset: Number of orders to skip for pagination.
    :returns: Dict with ``orders`` list and ``total`` count.
    """
    orders, total = await order_service.list_orders(db, session_id, status, limit, offset)
    return {"orders": orders, "total": total}


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get Order",
    description="Retrieve details of a specific order.",
)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the full details of a single order, including all line items.

    :param order_id: UUID of the order to retrieve.
    :returns: OrderResponse with items, status, and submitter info.
    :raises NotFoundException: If no order with the given ID exists.
    """
    return await order_service.get_order(db, order_id)


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="Update Order Status",
    description="Transition an order's status (Staff/Admin only).",
)
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("order:status-update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Transition an order through its lifecycle (e.g., RECEIVED → PREPARING → READY).
    Broadcasts the update to admin, staff, and session WebSocket rooms.

    :param order_id: UUID of the order to update.
    :param body: The target status to transition to.
    :returns: Updated OrderResponse.
    :raises BadRequestException: If the requested transition is not valid.
    """
    order = await order_service.update_order_status(db, order_id, body.status)
    try:
        order_dict = OrderResponse.model_validate(order).model_dump(mode="json")
        restaurant_id = order.session.table.restaurant_id
        await ws_manager.broadcast_to_room(f"admin:{restaurant_id}", "order:updated", order_dict)
        await ws_manager.broadcast_to_room(f"staff:{restaurant_id}", "order:updated", order_dict)
        await ws_manager.broadcast_to_room(f"session:{order.session_id}", "order:updated", order_dict)
    except Exception as e:
        pass
    return order


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel Order",
    description="Cancel an order with a reason (Staff/Admin only).",
)
async def cancel_order(
    order_id: UUID,
    body: OrderCancelRequest,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("order:cancel")),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel an order with a mandatory reason string. Restricted to staff and admins.
    Broadcasts the cancellation to admin, staff, and session WebSocket rooms.

    :param order_id: UUID of the order to cancel.
    :param body: Cancellation payload containing the reason (3–500 characters).
    :returns: Updated OrderResponse with CANCELLED status and reason.
    :raises BadRequestException: If the order is already completed or cancelled.
    """
    order = await order_service.cancel_order(db, order_id, current_user, body.reason)
    try:
        order_dict = OrderResponse.model_validate(order).model_dump(mode="json")
        restaurant_id = order.session.table.restaurant_id
        await ws_manager.broadcast_to_room(f"admin:{restaurant_id}", "order:updated", order_dict)
        await ws_manager.broadcast_to_room(f"staff:{restaurant_id}", "order:updated", order_dict)
        await ws_manager.broadcast_to_room(f"session:{order.session_id}", "order:updated", order_dict)
    except Exception as e:
        pass
    return order
