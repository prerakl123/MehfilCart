"""Menu router -- browse menu (guests) and manage menu (admin)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.menu import (
    CategoryCreate, CategoryResponse, CategoryUpdate,
    MenuItemCreate, MenuItemResponse, MenuItemUpdate, MenuResponse,
)
from app.services import menu_service

router = APIRouter(tags=["Menu"])


# -- Public/Guest Endpoints --

@router.get(
    "/restaurants/{restaurant_id}/menu",
    response_model=MenuResponse,
    summary="Get Full Menu",
    description="Retrieve the full menu for a restaurant (available items only).",
)
async def get_menu(
    restaurant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the full public menu (categories and items) for a given restaurant.
    Available to all users without authentication.

    :param restaurant_id: UUID of the target restaurant.
    :returns: MenuResponse grouping all active categories and their menu items.
    """
    categories = await menu_service.get_categories(db, restaurant_id)
    items = await menu_service.get_menu_items(db, restaurant_id, available_only=False)
    return MenuResponse(
        restaurant_id=restaurant_id,
        categories=categories,
        items=items,
    )


@router.get(
    "/restaurants/{restaurant_id}/categories",
    response_model=list[CategoryResponse],
    summary="Get Categories",
    description="Retrieve all active categories for a restaurant.",
)
async def get_categories(
    restaurant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all active menu categories for a restaurant, ordered by display_order.

    :param restaurant_id: UUID of the target restaurant.
    :returns: List of CategoryResponse objects.
    """
    return await menu_service.get_categories(db, restaurant_id)


# -- Admin Endpoints --

@router.get(
    "/restaurants/{restaurant_id}/menu/admin",
    response_model=MenuResponse,
    summary="Get Menu (Admin)",
    description="Retrieve the full menu including unavailable items (Admin only).",
    dependencies=[Depends(require_permission("menu:manage"))],
)
async def get_menu_admin(
    restaurant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the full menu including items marked unavailable. Restricted to admins.

    :param restaurant_id: UUID of the target restaurant.
    :returns: MenuResponse with all categories and all items regardless of availability.
    """
    categories = await menu_service.get_categories(db, restaurant_id)
    # Fetch all items, not just available ones
    query = (
        select(menu_service.MenuItem)
        .join(menu_service.Category)
        .where(menu_service.Category.restaurant_id == restaurant_id)
        .order_by(menu_service.MenuItem.display_order)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return MenuResponse(
        restaurant_id=restaurant_id,
        categories=categories,
        items=items,
    )


@router.post(
    "/restaurants/{restaurant_id}/categories",
    response_model=CategoryResponse,
    status_code=201,
    summary="Create Category",
    description="Create a new menu category (Admin only).",
)
async def create_category(
    restaurant_id: UUID,
    body: CategoryCreate,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("menu:manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new menu category for a restaurant. Requires the ``menu:manage`` permission.

    :param restaurant_id: UUID of the restaurant that owns the category.
    :param body: Category creation payload with name, display order, and optional icon.
    :returns: The newly created CategoryResponse.
    """
    return await menu_service.create_category(db, restaurant_id, body)


@router.patch(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Update Category",
    description="Update a menu category (Admin only).",
)
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("menu:manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Partially update a menu category's name, display order, icon, or active status.

    :param category_id: UUID of the category to update.
    :param body: Fields to update; only provided fields are applied.
    :returns: Updated CategoryResponse.
    :raises NotFoundException: If no category with the given ID exists.
    """
    return await menu_service.update_category(db, category_id, body)


@router.post(
    "/restaurants/{restaurant_id}/menu/items",
    response_model=MenuItemResponse,
    status_code=201,
    summary="Create Menu Item",
    description="Create a new menu item (Admin only).",
)
async def create_menu_item(
    restaurant_id: UUID,
    body: MenuItemCreate,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("menu:manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new menu item under an existing category. Requires ``menu:manage`` permission.

    :param restaurant_id: UUID of the restaurant; used to verify the category ownership.
    :param body: Item creation payload including name, price, diet type, and category.
    :returns: The newly created MenuItemResponse.
    :raises BadRequestException: If the specified category does not belong to the restaurant.
    """
    return await menu_service.create_menu_item(db, restaurant_id, body)


@router.patch(
    "/menu/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Update Menu Item",
    description="Update a menu item's properties (Admin only).",
)
async def update_menu_item(
    item_id: UUID,
    body: MenuItemUpdate,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("menu:manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Partially update a menu item's properties such as price, availability, or description.

    :param item_id: UUID of the menu item to update.
    :param body: Fields to update; only provided fields are applied.
    :returns: Updated MenuItemResponse.
    :raises NotFoundException: If no item with the given ID exists.
    """
    return await menu_service.update_menu_item(db, item_id, body)


@router.delete(
    "/menu/items/{item_id}",
    response_model=MessageResponse,
    summary="Delete Menu Item",
    description="Soft-delete a menu item by marking it unavailable (Admin only).",
)
async def delete_menu_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("menu:manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-delete a menu item by marking it as unavailable rather than removing the record.

    :param item_id: UUID of the menu item to deactivate.
    :returns: Confirmation message.
    :raises NotFoundException: If no item with the given ID exists.
    """
    await menu_service.delete_menu_item(db, item_id)
    return MessageResponse(message="Menu item deleted.")
