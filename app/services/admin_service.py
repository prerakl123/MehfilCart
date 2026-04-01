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
from app.schemas.admin import (
    TableCreate, TableUpdate, StaffCreate,
    RestaurantDashboardStats, SuperAdminDashboardStats,
    HourlyMetric, CategoryMetric, ItemMetric, RestaurantPerformanceMetric, DailyPlatformMetric
)
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


async def get_dashboard_stats(db: AsyncSession, restaurant_id: UUID) -> RestaurantDashboardStats:
    """Compute dashboard statistics for a restaurant."""
    from datetime import timedelta
    from sqlalchemy.orm import aliased
    from app.models.menu import MenuItem, Category
    from app.models.order import OrderItem, OrderStatus

    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
    last_week_start = today_start - timedelta(days=7)
    last_week_end = last_week_start + timedelta(days=1)

    # Active sessions & tables
    tables_res = await db.execute(
        select(Table.id, Table.capacity).where(
            Table.restaurant_id == restaurant_id, Table.is_active == True
        )
    )
    all_tables = tables_res.all()
    total_tables = len(all_tables)

    sessions_res = await db.execute(
        select(Table.id).join(Session, Session.table_id == Table.id).where(
            Table.restaurant_id == restaurant_id,
            Session.status.in_([SessionStatus.ACTIVE, SessionStatus.CREATED])
        )
    )
    active_tables_ids = {row[0] for row in sessions_res.all()}
    active_tables = len(active_tables_ids)
    active_sessions = active_tables
    table_occupancy_rate = round((active_tables / total_tables * 100), 2) if total_tables > 0 else 0.0

    # Orders & Revenue Today
    today_orders_res = await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .join(Session).join(Table).where(
            Table.restaurant_id == restaurant_id,
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED,
        )
    )
    row_today = today_orders_res.one()
    orders_today = row_today[0] or 0
    revenue_today = float(row_today[1] or 0)

    # Orders & Revenue Last Week (for trend)
    last_week_orders_res = await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .join(Session).join(Table).where(
            Table.restaurant_id == restaurant_id,
            Order.submitted_at >= last_week_start,
            Order.submitted_at < last_week_end,
            Order.status != OrderStatus.CANCELLED,
        )
    )
    row_last_week = last_week_orders_res.one()
    orders_last_week = row_last_week[0] or 0
    revenue_last_week = float(row_last_week[1] or 0)

    orders_trend = ((orders_today - orders_last_week) / orders_last_week * 100) if orders_last_week > 0 else (100.0 if orders_today > 0 else 0.0)
    revenue_trend = ((revenue_today - revenue_last_week) / revenue_last_week * 100) if revenue_last_week > 0 else (100.0 if revenue_today > 0 else 0.0)

    aov = (revenue_today / orders_today) if orders_today > 0 else 0.0

    # Live Orders statuses
    live_res = await db.execute(
        select(Order.status, func.count(Order.id))
        .join(Session).join(Table).where(
            Table.restaurant_id == restaurant_id,
            Order.status.in_([OrderStatus.PREPARING, OrderStatus.READY])
        ).group_by(Order.status)
    )
    live_counts = dict(live_res.all())
    preparing = live_counts.get(OrderStatus.PREPARING, 0)
    ready = live_counts.get(OrderStatus.READY, 0)

    # Hourly Trend Today
    hourly_res = await db.execute(
        select(
            func.extract('hour', Order.submitted_at).label('hr'),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.count(Order.id)
        )
        .join(Session).join(Table).where(
            Table.restaurant_id == restaurant_id,
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED,
        ).group_by('hr').order_by('hr')
    )
    hourly_trend = []
    for hr, rev, ords in hourly_res.all():
        ampm = "AM" if hr < 12 else "PM"
        hr_disp = int(hr) % 12 or 12
        hourly_trend.append(HourlyMetric(time=f"{hr_disp} {ampm}", revenue=float(rev), orders=int(ords)))

    # Category Breakdown
    cat_res = await db.execute(
        select(
            Category.name,
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0)
        )
        .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Category, MenuItem.category_id == Category.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Session, Order.session_id == Session.id)
        .join(Table, Session.table_id == Table.id)
        .where(
            Table.restaurant_id == restaurant_id,
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED,
        ).group_by(Category.name)
    )
    cat_rows = cat_res.all()
    cat_total = sum(float(r[1]) for r in cat_rows)
    category_sales = []
    for cat_name, amt in cat_rows:
        rev = float(amt)
        pct = (rev / cat_total * 100) if cat_total > 0 else 0
        category_sales.append(CategoryMetric(category=cat_name, revenue=rev, percentage=round(pct, 2)))

    # Items performance
    item_res = await db.execute(
        select(
            MenuItem.name,
            func.sum(OrderItem.quantity).label('qty'),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label('rev')
        )
        .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Session, Order.session_id == Session.id)
        .join(Table, Session.table_id == Table.id)
        .where(
            Table.restaurant_id == restaurant_id,
            Order.status != OrderStatus.CANCELLED,
            Order.submitted_at >= today_start - timedelta(days=30)
        ).group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).desc())
    )
    items_list = item_res.all()
    top_items = [ItemMetric(name=r[0], orders=int(r[1] or 0), revenue=float(r[2] or 0)) for r in items_list[:5]]
    
    # dead_stock (bottom 5 but ascending) 
    dead_stock_sql = await db.execute(
        select(
            MenuItem.name,
            func.sum(OrderItem.quantity).label('qty'),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label('rev')
        )
        .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Session, Order.session_id == Session.id)
        .join(Table, Session.table_id == Table.id)
        .where(
            Table.restaurant_id == restaurant_id,
            Order.status != OrderStatus.CANCELLED,
            Order.submitted_at >= today_start - timedelta(days=30)
        ).group_by(MenuItem.name).order_by(func.sum(OrderItem.quantity).asc()).limit(5)
    )
    dead_stock = [ItemMetric(name=r[0], orders=int(r[1] or 0), revenue=float(r[2] or 0)) for r in dead_stock_sql.all()]

    return RestaurantDashboardStats(
        revenue_today=revenue_today,
        revenue_trend=round(revenue_trend, 2),
        orders_today=orders_today,
        orders_trend=round(orders_trend, 2),
        active_sessions=active_sessions,
        total_tables=total_tables,
        active_tables=active_tables,
        table_occupancy_rate=table_occupancy_rate,
        live_orders_preparing=preparing,
        live_orders_ready=ready,
        average_order_value=round(aov, 2),
        hourly_trend=hourly_trend,
        category_sales=category_sales,
        top_items=top_items,
        dead_stock=dead_stock
    )


async def get_global_dashboard_stats(db: AsyncSession) -> SuperAdminDashboardStats:
    """Compute global platform dashboard statistics for Super Admin."""
    from datetime import timedelta
    from app.models.order import OrderStatus

    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=timezone.utc)
    last_week_start = today_start - timedelta(days=7)
    last_week_end = last_week_start + timedelta(days=1)

    # GMV & Orders Today
    today_res = await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
        .where(
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED,
        )
    )
    r_today = today_res.one()
    orders_today = r_today[0] or 0
    gmv_today = float(r_today[1] or 0)

    # GMV Last Week
    last_week_res = await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0))
        .where(
            Order.submitted_at >= last_week_start,
            Order.submitted_at < last_week_end,
            Order.status != OrderStatus.CANCELLED,
        )
    )
    r_last_week = last_week_res.one()
    gmv_last_week = float(r_last_week[0] or 0)
    gmv_trend = ((gmv_today - gmv_last_week) / gmv_last_week * 100) if gmv_last_week > 0 else (100.0 if gmv_today > 0 else 0.0)

    # Active Restaurants (that have received an order today)
    rest_res = await db.execute(
        select(func.count(func.distinct(Table.restaurant_id)))
        .join(Session, Session.table_id == Table.id)
        .join(Order, Order.session_id == Session.id)
        .where(
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED
        )
    )
    total_active_restaurants = rest_res.scalar() or 0

    # Global active sessions
    sess_res = await db.execute(
        select(func.count(Session.id)).where(Session.status.in_([SessionStatus.ACTIVE, SessionStatus.CREATED]))
    )
    global_active_sessions = sess_res.scalar() or 0

    # Restaurant Performance (Top and Lowest) - over last 30 days
    sentinel_id = UUID("00000000-0000-0000-0000-000000000000")
    perf_res = await db.execute(
        select(
            Restaurant.id, Restaurant.name, 
            func.coalesce(func.sum(Order.total_amount), 0).label('rev'), 
            func.count(Order.id).label('ords')
        )
        .join(Table, Table.restaurant_id == Restaurant.id)
        .join(Session, Session.table_id == Table.id)
        .join(Order, Order.session_id == Session.id)
        .where(
            Order.submitted_at >= today_start - timedelta(days=30),
            Order.status != OrderStatus.CANCELLED,
            Restaurant.id != sentinel_id
        ).group_by(Restaurant.id).order_by(func.coalesce(func.sum(Order.total_amount), 0).desc())
    )
    perf_list = perf_res.all()
    
    top_restaurants = [
        RestaurantPerformanceMetric(id=r[0], name=r[1], revenue=float(r[2]), orders=int(r[3]))
        for r in perf_list[:5]
    ]
    lowest_restaurants = [
        RestaurantPerformanceMetric(id=r[0], name=r[1], revenue=float(r[2]), orders=int(r[3]))
        for r in reversed(perf_list[-5:])
    ] if len(perf_list) > 5 else []

    # Platform growth trend (last 7 days daily GMV)
    platform_trend = []
    for i in range(6, -1, -1):
        d_start = today_start - timedelta(days=i)
        d_end = d_start + timedelta(days=1)
        d_res = await db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0))
            .where(
                Order.submitted_at >= d_start,
                Order.submitted_at < d_end,
                Order.status != OrderStatus.CANCELLED,
            )
        )
        d_row = d_res.one()
        platform_trend.append(DailyPlatformMetric(
            date=d_start.strftime("%b %d"),
            orders=d_row[0] or 0,
            revenue=float(d_row[1] or 0)
        ))

    # Global Hourly trend (Today)
    hourly_res = await db.execute(
        select(
            func.extract('hour', Order.submitted_at).label('hr'),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.count(Order.id)
        )
        .where(
            Order.submitted_at >= today_start,
            Order.status != OrderStatus.CANCELLED,
        ).group_by('hr').order_by('hr')
    )
    global_hourly_trend = []
    for hr, rev, ords in hourly_res.all():
        ampm = "AM" if hr < 12 else "PM"
        hr_disp = int(hr) % 12 or 12
        global_hourly_trend.append(HourlyMetric(time=f"{hr_disp} {ampm}", revenue=float(rev), orders=int(ords)))

    return SuperAdminDashboardStats(
        total_gmv_today=gmv_today,
        gmv_trend=round(gmv_trend, 2),
        total_active_restaurants=total_active_restaurants,
        total_orders_today=orders_today,
        global_active_sessions=global_active_sessions,
        top_restaurants=top_restaurants,
        lowest_restaurants=lowest_restaurants,
        global_hourly_trend=global_hourly_trend,
        platform_growth_trend=platform_trend
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
    from app.core.permissions import Role
    result = await db.execute(
        select(UserRole)
        .options(selectinload(UserRole.user))
        .where(
            UserRole.restaurant_id == restaurant_id,
            UserRole.role.in_([Role.SUPER_ADMIN, Role.RESTAURANT_ADMIN, Role.WAITER])
        )
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
