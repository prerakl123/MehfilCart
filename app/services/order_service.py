"""
Order service -- submit cart as order, status transitions, cancellation.
"""

from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException, ForbiddenException, NotFoundException,
)
from app.models.order import Order, OrderItem, OrderStatus
from app.models.session import Session, SessionStatus
from app.models.session_event import SessionEventType
from app.models.user import User
from app.services import cart_service, session_event_service


def _order_load_options():
    """Standard eager-load options for Order queries returned to the API."""
    return [
        selectinload(Order.items).selectinload(OrderItem.menu_item),
        selectinload(Order.items).selectinload(OrderItem.adder),
        selectinload(Order.submitter),
        selectinload(Order.session).selectinload(Session.table),
    ]


async def submit_order(
    db: AsyncSession,
    redis: aioredis.Redis,
    session: Session,
    user: User,
    special_notes: str | None = None,
) -> Order:
    """
    Submit the current cart as a finalized order.
    Only the Host can submit. Converts Redis cart items into DB OrderItems.
    """
    if str(session.host_user_id) != str(user.id):
        raise ForbiddenException("Only the session host can submit orders.")

    if session.status not in (
        SessionStatus.CREATED,
        SessionStatus.ACTIVE,
        SessionStatus.SUBMITTED,
        SessionStatus.IN_PROGRESS
    ):
        raise BadRequestException(
            f"Cannot submit order in {session.status.value} state.")

    # Fetch cart from Redis
    cart = await cart_service.get_cart(redis, session.id)
    if not cart.items:
        raise BadRequestException(
            "Cart is empty. Add items before submitting.")

    now = datetime.now(timezone.utc)

    order = Order(
        session_id=session.id,
        status=OrderStatus.RECEIVED,
        special_notes=special_notes,
        submitted_at=now,
        submitted_by=user.id,
        total_amount=cart.total,
    )
    db.add(order)
    await db.flush()

    # Convert cart items to persistent OrderItems
    for cart_item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=cart_item.menu_item_id,
            added_by=cart_item.added_by_id,
            quantity=cart_item.quantity,
            unit_price=cart_item.menu_item_price,
            customizations=cart_item.customizations,
            notes=cart_item.notes,
        )
        db.add(order_item)

    # Update session status
    session.status = SessionStatus.SUBMITTED
    await db.flush()

    await session_event_service.log_event(
        db, session.id, SessionEventType.ORDER_SUBMITTED, actor_id=user.id,
        payload={
            "order_id": str(order.id),
            "total_amount": float(cart.total),
            "item_count": len(cart.items),
        },
    )

    # Clear the Redis cart
    await cart_service.clear_cart(redis, session.id)

    # Re-query with eager loads for response serialization
    result = await db.execute(
        select(Order).options(*_order_load_options()
                              ).where(Order.id == order.id)
    )
    return result.scalar_one()


async def get_order(db: AsyncSession, order_id: UUID) -> Order:
    """Fetch an order by ID."""
    result = await db.execute(
        select(Order).options(*_order_load_options()
                              ).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundException("Order not found.")
    return order


async def list_orders(
    db: AsyncSession,
    session_id: UUID | None = None,
    status: OrderStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Order], int]:
    """List orders with optional filters. Returns (orders, total_count)."""
    query = select(Order).options(*_order_load_options())
    if session_id:
        query = query.where(Order.session_id == session_id)
    if status:
        query = query.where(Order.status == status)

    query = query.order_by(Order.submitted_at.desc()
                           ).limit(limit).offset(offset)
    result = await db.execute(query)
    orders = result.scalars().all()

    # Get total count
    count_query = select(func.count(Order.id))
    if session_id:
        count_query = count_query.where(Order.session_id == session_id)
    if status:
        count_query = count_query.where(Order.status == status)

    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    return list(orders), total_count


async def update_order_status(
    db: AsyncSession,
    order_id: UUID,
    new_status: OrderStatus,
    actor_id: UUID | None = None,
) -> Order:
    """Transition an order's status. Enforces valid transitions."""
    order = await get_order(db, order_id)

    valid_transitions = {
        OrderStatus.RECEIVED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
        OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
        OrderStatus.READY: [OrderStatus.SERVED],
        OrderStatus.SERVED: [OrderStatus.COMPLETED],
    }

    allowed = valid_transitions.get(order.status, [])
    if new_status not in allowed:
        raise BadRequestException(
            f"Cannot transition from {order.status.value} to {new_status.value}."
        )

    from_status = order.status
    order.status = new_status
    await db.flush()

    await session_event_service.log_event(
        db, order.session_id, SessionEventType.ORDER_STATUS_CHANGED, actor_id=actor_id,
        payload={
            "order_id": str(order.id),
            "from_status": from_status.value,
            "to_status": new_status.value,
        },
    )
    return order


async def cancel_order(
    db: AsyncSession,
    order_id: UUID,
    cancelled_by: User,
    reason: str,
) -> Order:
    """Cancel an order with a stated reason. Staff/Admin only (enforced at router)."""
    order = await get_order(db, order_id)

    if order.status in (OrderStatus.COMPLETED, OrderStatus.CANCELLED):
        raise BadRequestException(f"Order is already {order.status.value}.")

    order.status = OrderStatus.CANCELLED
    order.cancelled_by = cancelled_by.id
    order.cancel_reason = reason
    await db.flush()

    await session_event_service.log_event(
        db, order.session_id, SessionEventType.ORDER_CANCELLED, actor_id=cancelled_by.id,
        payload={"order_id": str(order.id), "reason": reason},
    )
    return order
