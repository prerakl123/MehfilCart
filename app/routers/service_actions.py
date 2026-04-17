"""Service actions router."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_any_role
from app.core.permissions import Role
from app.models.user import User
from app.schemas.service_action import ServiceActionCreate, ServiceActionResponse
from app.services import service_action_service

router = APIRouter(tags=["Service Actions"])


@router.post("/sessions/{session_id}/service-actions", response_model=ServiceActionResponse)
async def create_service_action(
    session_id: UUID,
    body: ServiceActionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new service action (e.g., Call Waiter)."""
    # Any authenticated user could be a guest, so get_current_user is fine. 
    # Business logic verifies session membership.
    return await service_action_service.create_service_action(
        db, session_id, current_user, body.action_type
    )


@router.get("/restaurants/{restaurant_id}/service-actions", response_model=List[ServiceActionResponse])
async def list_pending_actions(
    restaurant_id: UUID,
    current_user: User = Depends(require_any_role(Role.WAITER, Role.RESTAURANT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """List pending/claimed service actions for a restaurant (for staff UI)."""
    # In a real app we'd verify current_user belongs to this restaurant
    actions = await service_action_service.get_pending_actions(db, restaurant_id)
    
    # Enrichment mapping for the response
    out = []
    for action in actions:
        resp = ServiceActionResponse.model_validate(action)
        resp.table_label = action.table.label if action.table else None
        resp.requested_by_name = action.requested_by.display_name if action.requested_by else None
        resp.claimed_by_name = action.claimed_by.display_name if action.claimed_by else None
        out.append(resp)
        
    return out


@router.patch("/service-actions/{action_id}/claim", response_model=ServiceActionResponse)
async def claim_action(
    action_id: UUID,
    current_user: User = Depends(require_any_role(Role.WAITER, Role.RESTAURANT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Staff claims an action."""
    action = await service_action_service.claim_service_action(db, action_id, current_user)
    resp = ServiceActionResponse.model_validate(action)
    return resp


@router.patch("/service-actions/{action_id}/complete", response_model=ServiceActionResponse)
async def complete_action(
    action_id: UUID,
    current_user: User = Depends(require_any_role(Role.WAITER, Role.RESTAURANT_ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Staff completes an action."""
    action = await service_action_service.complete_service_action(db, action_id, current_user)
    resp = ServiceActionResponse.model_validate(action)
    return resp
