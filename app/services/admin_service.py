"""
Admin service -- dashboard stats, table management, staff management, config.
"""

from datetime import datetime, timezone, date
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, BadRequestException, ConflictException
from app.models.order import Order, OrderStatus
from app.models.restaurant import Restaurant, UserRole
from app.models.session import Session, SessionStatus
from app.models.table import Table
from app.models.user import User
from app.schemas.admin import DashboardStats, TableCreate, TableUpdate, StaffCreate
from app.schemas.restaurant import RestaurantCreate, RestaurantUpdate
from app.utils.phone import normalize_phone, is_valid_phone
from app.utils.qr import generate_table_qr_url


# -- Restaurant Management (Super Admin) --

async def create_restaurant(
    db: AsyncSession, data: RestaurantCreate,
) -> Restaurant:
    """Create a new restaurant on the platform."""
    # Check slug uniqueness
    result = await db.execute(
        select(Restaurant).where(Restaurant.slug == data.slug)
    )
    if result.scalar_one_or_none():
        raise ConflictException(
            f"Restaurant with slug '{data.slug}' already exists.")

    restaurant = Restaurant(
        name=data.name,
        slug=data.slug,
        address=data.address,
        phone=data.phone,
        logo_url=data.logo_url,
        config={},
    )
    db.add(restaurant)
    await db.flush()
    return restaurant


async def list_restaurants(db: AsyncSession) -> list[Restaurant]:
    """List all restaurants on the platform (excludes the sentinel __platform__ entry)."""
    sentinel_id = UUID("00000000-0000-0000-0000-000000000000")
    result = await db.execute(
        select(Restaurant)
        .where(Restaurant.id != sentinel_id)
        .order_by(Restaurant.name)
    )
    return list(result.scalars().all())


async def get_restaurant(db: AsyncSession, restaurant_id: UUID) -> Restaurant:
    """Fetch a single restaurant by ID."""
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id)
    )
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundException("Restaurant not found.")
    return restaurant


async def update_restaurant(
    db: AsyncSession, restaurant_id: UUID, data: RestaurantUpdate,
) -> Restaurant:
    """Update restaurant properties."""
    restaurant = await get_restaurant(db, restaurant_id)

    update_data = data.model_dump(exclude_unset=True)

    # If slug is being changed, check uniqueness
    if "slug" in update_data:
        result = await db.execute(
            select(Restaurant).where(
                Restaurant.slug == update_data["slug"],
                Restaurant.id != restaurant_id,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictException(
                f"Slug '{update_data['slug']}' is already taken.")

    for field, value in update_data.items():
        setattr(restaurant, field, value)

    await db.flush()
    return restaurant


async def delete_restaurant(db: AsyncSession, restaurant_id: UUID) -> None:
    """Delete a restaurant (Super Admin only)."""
    restaurant = await get_restaurant(db, restaurant_id)
    await db.delete(restaurant)
    await db.flush()

# -- Dashboard --


async def get_dashboard_stats(db: AsyncSession, restaurant_id: UUID) -> DashboardStats:
    """Compute dashboard statistics for a restaurant."""
    today_start = datetime.combine(
        date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    # Active sessions count
    active_result = await db.execute(
        select(func.count(Session.id))
        .join(Table)
        .where(
            Table.restaurant_id == restaurant_id,
            Session.status.in_([SessionStatus.ACTIVE, SessionStatus.CREATED]),
        )
    )
    active_sessions = active_result.scalar() or 0

    # Today's orders and revenue
    orders_result = await db.execute(
        select(func.count(Order.id), func.coalesce(
            func.sum(Order.total_amount), 0))
        .join(Session)
        .join(Table)
        .where(
            Table.restaurant_id == restaurant_id,
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED,
        )
    )
    row = orders_result.one()
    total_orders_today = row[0] or 0
    revenue_today = float(row[1] or 0)

    # Table count
    tables_result = await db.execute(
        select(func.count(Table.id)).where(
            Table.restaurant_id == restaurant_id, Table.is_active == True,
        )
    )
    total_tables = tables_result.scalar() or 0

    # Staff count
    staff_result = await db.execute(
        select(func.count(UserRole.id)).where(
            UserRole.restaurant_id == restaurant_id,
        )
    )
    active_staff = staff_result.scalar() or 0

    return DashboardStats(
        active_sessions=active_sessions,
        total_orders_today=total_orders_today,
        revenue_today=revenue_today,
        total_tables=total_tables,
        active_staff=active_staff,
    )


# -- Table Management --

async def create_table(
    db: AsyncSession, restaurant_id: UUID, data: TableCreate,
) -> Table:
    """Create a new table and generate its QR code URL."""
    table = Table(
        restaurant_id=restaurant_id,
        label=data.label,
        capacity=data.capacity,
    )
    db.add(table)
    await db.flush()

    # Generate QR URL
    table.qr_code_url = generate_table_qr_url(str(restaurant_id), str(table.id))
    await db.flush()
    return table


async def update_table(
    db: AsyncSession, table_id: UUID, data: TableUpdate,
) -> Table:
    """Update table properties."""
    result = await db.execute(select(Table).where(Table.id == table_id))
    table = result.scalar_one_or_none()
    if table is None:
        raise NotFoundException("Table not found.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(table, field, value)

    await db.flush()
    return table


async def delete_table(db: AsyncSession, table_id: UUID) -> None:
    """Delete a table."""
    result = await db.execute(select(Table).where(Table.id == table_id))
    table = result.scalar_one_or_none()
    if table is None:
        raise NotFoundException("Table not found.")
    await db.delete(table)
    await db.flush()


async def list_tables(db: AsyncSession, restaurant_id: UUID) -> list[Table]:
    """List all tables for a restaurant."""
    result = await db.execute(
        select(Table).where(Table.restaurant_id ==
                            restaurant_id).order_by(Table.label)
    )
    return list(result.scalars().all())


# -- Staff Management --

async def add_staff(
    db: AsyncSession, restaurant_id: UUID, data: StaffCreate,
) -> UserRole:
    """Add a staff member to a restaurant. Creates user if needed."""
    phone = normalize_phone(data.phone)
    if not is_valid_phone(phone):
        raise BadRequestException("Invalid phone number.")

    # Get or create user
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(phone=phone, display_name=data.display_name)
        db.add(user)
        await db.flush()

    # Check if already assigned
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.restaurant_id == restaurant_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictException("User is already assigned to this restaurant.")

    role = UserRole(
        user_id=user.id,
        restaurant_id=restaurant_id,
        role=data.role,
    )
    db.add(role)
    await db.flush()
    return role


async def remove_staff(db: AsyncSession, role_id: UUID) -> None:
    """Remove a staff member's role assignment."""
    result = await db.execute(select(UserRole).where(UserRole.id == role_id))
    role = result.scalar_one_or_none()
    if role is None:
        raise NotFoundException("Staff assignment not found.")
    await db.delete(role)
    await db.flush()


async def list_staff(db: AsyncSession, restaurant_id: UUID) -> list[UserRole]:
    """List all staff members for a restaurant."""
    result = await db.execute(
        select(UserRole).where(UserRole.restaurant_id == restaurant_id)
    )
    return list(result.scalars().all())


# -- Restaurant Config --

async def update_config(
    db: AsyncSession, restaurant_id: UUID, config_update: dict,
) -> Restaurant:
    """Update restaurant configuration (session timeouts, max guests, etc.)."""
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundException("Restaurant not found.")

    current_config = restaurant.config or {}
    current_config.update(config_update)
    restaurant.config = current_config
    await db.flush()
    return restaurant


async def list_orders(db: AsyncSession, restaurant_id: UUID) -> list[Order]:
    """List all orders for a given restaurant's tables within the last 24 hours."""
    from datetime import datetime, timedelta, timezone
    from app.models.order import OrderItem
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)

    query = (
        select(Order)
        .join(Session, Order.session_id == Session.id)
        .join(Table, Session.table_id == Table.id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.menu_item),
            selectinload(Order.items).selectinload(OrderItem.adder),
            selectinload(Order.submitter),
        )
        .where(
            Table.restaurant_id == restaurant_id,
            Order.submitted_at >= cutoff
        )
        .order_by(Order.submitted_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_sessions(db: AsyncSession, restaurant_id: UUID) -> list[Session]:
    """List all active or recent sessions for a given restaurant."""
    from datetime import datetime, timedelta, timezone
    from app.models.session import SessionMember
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)

    query = (
        select(Session)
        .join(Table, Session.table_id == Table.id)
        .options(
            selectinload(Session.members).selectinload(SessionMember.user),
            selectinload(Session.table),
        )
        .where(
            Table.restaurant_id == restaurant_id,
            (Session.status != SessionStatus.CLOSED) | (
                Session.created_at >= cutoff)
        )
        .order_by(Session.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())
