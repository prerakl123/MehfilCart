"""Admin router -- dashboard, table management, staff management, restaurant CRUD, config."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_any_role
from app.models.user import User
from app.schemas.admin import (
    DashboardStats, RestaurantConfigUpdate, StaffCreate, StaffResponse,
    TableCreate, TableResponse, TableUpdate,
)
from app.schemas.auth import MessageResponse
from app.schemas.order import OrderResponse
from app.schemas.restaurant import (
    RestaurantCreate, RestaurantResponse, RestaurantUpdate,
)
from app.schemas.session import SessionResponse
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])

# All admin endpoints require SUPER_ADMIN or RESTAURANT_ADMIN role
_admin_dep = Depends(require_any_role("SUPER_ADMIN", "RESTAURANT_ADMIN"))
_super_admin_dep = Depends(require_any_role("SUPER_ADMIN"))


# -- Restaurant CRUD (Super Admin) --

@router.get(
    "/restaurants",
    response_model=list[RestaurantResponse],
    summary="List Restaurants",
    description="List all restaurants on the platform (Super Admin only).",
    dependencies=[_super_admin_dep],
)
async def list_restaurants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_restaurants(db)


@router.get(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Get Restaurant",
    description="Get details of a specific restaurant.",
    dependencies=[_admin_dep],
)
async def get_restaurant(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_restaurant(db, restaurant_id)


@router.post(
    "/restaurants",
    response_model=RestaurantResponse,
    status_code=201,
    summary="Create Restaurant",
    description="Register a new restaurant on the platform (Super Admin only).",
    dependencies=[_super_admin_dep],
)
async def create_restaurant(
    body: RestaurantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.create_restaurant(db, body)


@router.patch(
    "/restaurants/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Update Restaurant",
    description="Update restaurant details (Super Admin only).",
    dependencies=[_super_admin_dep],
)
async def update_restaurant(
    restaurant_id: UUID,
    body: RestaurantUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.update_restaurant(db, restaurant_id, body)


@router.get(
    "/dashboard/{restaurant_id}",
    response_model=DashboardStats,
    summary="Dashboard Stats",
    description="Get overview statistics for the restaurant dashboard.",
    dependencies=[_admin_dep],
)
async def get_dashboard(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_dashboard_stats(db, restaurant_id)


# -- Tables --

@router.get(
    "/tables/{restaurant_id}",
    response_model=list[TableResponse],
    summary="List Tables",
    description="List all tables for a restaurant.",
    dependencies=[_admin_dep],
)
async def list_tables(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_tables(db, restaurant_id)


@router.post(
    "/tables/{restaurant_id}",
    response_model=TableResponse,
    status_code=201,
    summary="Create Table",
    description="Create a new table and generate a QR code URL.",
    dependencies=[_admin_dep],
)
async def create_table(
    restaurant_id: UUID,
    body: TableCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.create_table(db, restaurant_id, body)


@router.patch(
    "/tables/{restaurant_id}/{table_id}",
    response_model=TableResponse,
    summary="Update Table",
    description="Update a table's label, capacity, or active status.",
    dependencies=[_admin_dep],
)
async def update_table(
    restaurant_id: UUID,
    table_id: UUID,
    body: TableUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.update_table(db, table_id, body)


# -- Staff --

@router.get(
    "/staff/{restaurant_id}",
    response_model=list[StaffResponse],
    summary="List Staff",
    description="List all staff members assigned to a restaurant.",
    dependencies=[_admin_dep],
)
async def list_staff(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    roles = await admin_service.list_staff(db, restaurant_id)
    # Map to response schema
    result = []
    for r in roles:
        result.append(StaffResponse(
            id=r.id,
            user_id=r.user_id,
            phone=r.user.phone if r.user else "",
            display_name=r.user.display_name if r.user else None,
            role=r.role,
            restaurant_id=r.restaurant_id,
        ))
    return result


@router.post(
    "/staff/{restaurant_id}",
    response_model=MessageResponse,
    status_code=201,
    summary="Add Staff",
    description="Add a staff member to the restaurant.",
    dependencies=[_admin_dep],
)
async def add_staff(
    restaurant_id: UUID,
    body: StaffCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await admin_service.add_staff(db, restaurant_id, body)
    return MessageResponse(message="Staff member added successfully.")


@router.delete(
    "/staff/{role_id}",
    response_model=MessageResponse,
    summary="Remove Staff",
    description="Remove a staff member's role assignment.",
    dependencies=[_admin_dep],
)
async def remove_staff(
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await admin_service.remove_staff(db, role_id)
    return MessageResponse(message="Staff member removed.")


# -- Config --

@router.patch(
    "/config/{restaurant_id}",
    response_model=MessageResponse,
    summary="Update Config",
    description="Update restaurant session configuration.",
    dependencies=[_admin_dep],
)
async def update_config(
    restaurant_id: UUID,
    body: RestaurantConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await admin_service.update_config(
        db, restaurant_id, body.model_dump(exclude_unset=True),
    )
    return MessageResponse(message="Configuration updated.")


# -- Orders & Sessions (Admin View) --

@router.get(
    "/orders/{restaurant_id}",
    response_model=list[OrderResponse],
    summary="List Orders (Admin)",
    description="List all orders for a specific restaurant.",
    dependencies=[_admin_dep],
)
async def list_admin_orders(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_orders(db, restaurant_id)


@router.get(
    "/sessions/{restaurant_id}",
    response_model=list[SessionResponse],
    summary="List Sessions (Admin)",
    description="List all active/recent sessions for a specific restaurant.",
    dependencies=[_admin_dep],
)
async def list_admin_sessions(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_sessions(db, restaurant_id)
