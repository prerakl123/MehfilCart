"""
Menu service -- CRUD for categories and menu items.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.models.menu import Category, MenuItem
from app.schemas.menu import (
    CategoryCreate, CategoryUpdate, MenuItemCreate, MenuItemUpdate,
)


# -- Category Operations --

async def create_category(
    db: AsyncSession, restaurant_id: UUID, data: CategoryCreate,
) -> Category:
    """Create a new menu category for a restaurant."""
    category = Category(
        restaurant_id=restaurant_id,
        name=data.name,
        display_order=data.display_order,
        icon=data.icon,
    )
    db.add(category)
    await db.flush()
    return category


async def get_categories(db: AsyncSession, restaurant_id: UUID) -> list[Category]:
    """Fetch all active categories for a restaurant, ordered by display_order."""
    result = await db.execute(
        select(Category)
        .where(Category.restaurant_id == restaurant_id, Category.is_active == True)
        .order_by(Category.display_order)
    )
    return list(result.scalars().all())


async def update_category(
    db: AsyncSession, category_id: UUID, data: CategoryUpdate,
) -> Category:
    """Update a category's properties."""
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundException("Category not found.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    await db.flush()
    return category


# -- Menu Item Operations --

async def create_menu_item(
    db: AsyncSession, restaurant_id: UUID, data: MenuItemCreate,
) -> MenuItem:
    """Create a new menu item under a category."""
    # Verify category belongs to the restaurant
    result = await db.execute(
        select(Category).where(
            Category.id == data.category_id,
            Category.restaurant_id == restaurant_id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise BadRequestException(
            "Category not found or does not belong to this restaurant.")

    item = MenuItem(
        category_id=data.category_id,
        name=data.name,
        description=data.description,
        price=data.price,
        image_url=data.image_url,
        diet_type=data.diet_type,
        customizations=data.customizations,
        display_order=data.display_order,
    )
    db.add(item)
    await db.flush()
    return item


async def get_menu_items(
    db: AsyncSession,
    restaurant_id: UUID,
    category_id: UUID | None = None,
    available_only: bool = True,
) -> list[MenuItem]:
    """Fetch menu items for a restaurant, optionally filtered by category."""
    query = (
        select(MenuItem)
        .join(Category)
        .where(Category.restaurant_id == restaurant_id)
    )
    if category_id:
        query = query.where(MenuItem.category_id == category_id)
    if available_only:
        query = query.where(MenuItem.is_available == True)

    query = query.order_by(MenuItem.display_order)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_menu_item(db: AsyncSession, item_id: UUID) -> MenuItem:
    """Fetch a single menu item by ID."""
    result = await db.execute(select(MenuItem).where(MenuItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundException("Menu item not found.")
    return item


async def update_menu_item(
    db: AsyncSession, item_id: UUID, data: MenuItemUpdate,
) -> MenuItem:
    """Update a menu item's properties."""
    item = await get_menu_item(db, item_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.flush()
    return item


async def delete_menu_item(db: AsyncSession, item_id: UUID) -> None:
    """Soft-delete a menu item by marking it unavailable."""
    item = await get_menu_item(db, item_id)
    item.is_available = False
    await db.flush()
