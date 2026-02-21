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
    session = await session_service.get_session(db, session_id)
    return await order_service.submit_order(
        db, redis, session, current_user, body.special_notes,
    )


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
    return await order_service.update_order_status(db, order_id, body.status)


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
    return await order_service.cancel_order(db, order_id, current_user, body.reason)
