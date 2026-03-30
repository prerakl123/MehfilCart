"""Admin router -- dashboard, table management, staff management, restaurant CRUD, config."""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
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
    """
    List all registered restaurants on the platform, excluding the sentinel entry.
    Restricted to Super Admin.

    :returns: List of RestaurantResponse objects ordered by name.
    """
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
    """
    Retrieve the full details of a single restaurant by its ID.

    :param restaurant_id: UUID of the restaurant to look up.
    :returns: RestaurantResponse.
    :raises NotFoundException: If no restaurant with the given ID exists.
    """
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
    """
    Register a new restaurant on the platform. Restricted to Super Admin.

    :param body: Restaurant creation payload with name, slug, and optional contact details.
    :returns: The newly created RestaurantResponse.
    :raises ConflictException: If a restaurant with the same slug already exists.
    """
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
    """
    Update properties of an existing restaurant. Restricted to Super Admin.

    :param restaurant_id: UUID of the restaurant to update.
    :param body: Fields to update; only provided fields are applied.
    :returns: Updated RestaurantResponse.
    :raises ConflictException: If the new slug is already taken by another restaurant.
    """
    return await admin_service.update_restaurant(db, restaurant_id, body)


@router.delete(
    "/restaurants/{restaurant_id}",
    response_model=MessageResponse,
    summary="Delete Restaurant",
    description="Delete a restaurant (Super Admin only).",
    dependencies=[_super_admin_dep],
)
async def delete_restaurant(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a restaurant and its associated data. Restricted to Super Admin.

    :param restaurant_id: UUID of the restaurant to delete.
    :returns: Confirmation message.
    :raises NotFoundException: If no restaurant with the given ID exists.
    """
    await admin_service.delete_restaurant(db, restaurant_id)
    return MessageResponse(message="Restaurant deleted successfully.")


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
    """
    Return overview statistics for a restaurant dashboard: active sessions, orders, and revenue.

    :param restaurant_id: UUID of the restaurant whose stats to compute.
    :returns: DashboardStats with today's order count, revenue, and table/staff counts.
    """
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
    """
    List all tables belonging to a restaurant, ordered by label.

    :param restaurant_id: UUID of the restaurant.
    :returns: List of TableResponse objects.
    """
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
    """
    Create a new dining table for a restaurant and auto-generate its QR code URL.

    :param restaurant_id: UUID of the restaurant that will own the table.
    :param body: Table creation payload with label and capacity.
    :returns: The newly created TableResponse including the QR code URL.
    """
    return await admin_service.create_table(db, restaurant_id, body)


@router.get(
    "/tables/{restaurant_id}/{table_id}/qr",
    summary="Get Table QR Code",
    description="Returns the QR code PNG image for a table.",
    dependencies=[_admin_dep],
)
async def get_table_qr(
    restaurant_id: UUID,
    table_id: UUID,
    base_url: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and return the QR code PNG image for a specific table.
    The QR encodes the join URL that guests scan to start a session.

    :param restaurant_id: UUID of the restaurant that owns the table.
    :param table_id: UUID of the table to generate the QR code for.
    :param base_url: Optional override for the base URL; falls back to APP_BASE_URL.
    :returns: PNG image bytes with ``image/png`` media type.
    """
    from app.utils.qr import generate_table_qr_url, generate_qr_image
    from app.core.config import settings

    # Use provided base_url or fallback to app settings
    url = generate_table_qr_url(
        restaurant_id=str(restaurant_id),
        table_id=str(table_id),
        base_url=base_url or settings.APP_BASE_URL
    )
    img_bytes = generate_qr_image(url)
    return Response(content=img_bytes, media_type="image/png")


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
    """
    Update a table's label, seating capacity, or active status.

    :param restaurant_id: UUID of the restaurant (used for route scoping).
    :param table_id: UUID of the table to update.
    :param body: Fields to update; only provided fields are applied.
    :returns: Updated TableResponse.
    :raises NotFoundException: If no table with the given ID exists.
    """
    return await admin_service.update_table(db, table_id, body)


@router.delete(
    "/tables/{restaurant_id}/{table_id}",
    response_model=MessageResponse,
    summary="Delete Table",
    description="Delete a table.",
    dependencies=[_admin_dep],
)
async def delete_table(
    restaurant_id: UUID,
    table_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a table record from the restaurant.

    :param restaurant_id: UUID of the restaurant (used for route scoping).
    :param table_id: UUID of the table to delete.
    :returns: Confirmation message.
    :raises NotFoundException: If no table with the given ID exists.
    """
    await admin_service.delete_table(db, table_id)
    return MessageResponse(message="Table deleted successfully.")


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
    """
    List all staff members (admins and waiters) assigned to a restaurant.

    :param restaurant_id: UUID of the restaurant to query.
    :returns: List of StaffResponse objects with user and role details.
    """
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
    """
    Add a staff member to a restaurant. Creates a new User record if the phone is not registered.

    :param restaurant_id: UUID of the restaurant to assign the staff member to.
    :param body: Payload with phone, role, and optional display name.
    :returns: Confirmation message.
    :raises BadRequestException: If the phone number format is invalid.
    :raises ConflictException: If the user is already assigned to this restaurant.
    """
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
    """
    Remove a staff member's role assignment from the restaurant.

    :param role_id: UUID of the UserRole record to delete.
    :returns: Confirmation message.
    :raises NotFoundException: If no role assignment with the given ID exists.
    """
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
    """
    Update the restaurant's operational configuration (session timeouts, guest limits, etc.).

    :param restaurant_id: UUID of the restaurant to configure.
    :param body: Configuration fields to update; only provided fields are merged in.
    :returns: Confirmation message.
    :raises NotFoundException: If no restaurant with the given ID exists.
    """
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
    """
    List all orders placed at a restaurant's tables within the last 24 hours.

    :param restaurant_id: UUID of the restaurant to query.
    :returns: List of OrderResponse objects ordered by submission time descending.
    """
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
    """
    List all active and recent (last 12 hours) sessions for a restaurant.

    :param restaurant_id: UUID of the restaurant to query.
    :returns: List of SessionResponse objects ordered by creation time descending.
    """
    return await admin_service.list_sessions(db, restaurant_id)


# -- Name Change Requests --

@router.get(
    "/name-requests/{restaurant_id}",
    summary="List Name Change Requests",
    description="List all pending staff name change requests for a restaurant.",
    dependencies=[_admin_dep],
)
async def list_name_requests(
    restaurant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all pending staff display name change requests for a restaurant.

    :param restaurant_id: UUID of the restaurant to query.
    :returns: List of pending NameChangeRequest dicts with user and request details.
    """
    from app.services import user_service
    return await user_service.list_name_change_requests(db, restaurant_id)


@router.patch(
    "/name-requests/{request_id}",
    summary="Handle Name Change Request",
    description="Approve or reject a staff name change request.",
    dependencies=[_admin_dep],
)
async def handle_name_request(
    request_id: UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or reject a pending staff name change request.
    Approval immediately updates the staff member's display name.

    :param request_id: UUID of the NameChangeRequest to process.
    :param body: Dict with an ``"action"`` key set to ``"approve"`` or ``"reject"``.
    :returns: Updated request dict reflecting the new status.
    :raises NotFoundException: If no request with the given ID exists.
    :raises BadRequestException: If the request has already been processed or action is invalid.
    """
    from app.services import user_service
    action = body.get("action", "")
    return await user_service.handle_name_change_request(db, request_id, action)
