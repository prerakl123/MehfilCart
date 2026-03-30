"""
Mock database seeder for MehfilCart.

Populates all tables with realistic data for local development and testing.
Run from the project root:
    python docs/mock_db_creation.py

Prerequisites:
    - PostgreSQL running locally with the 'mehfilcart' database already created
    - All Alembic migrations applied (alembic upgrade head)
    - .env file present at the project root
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Allow importing the app package from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from asyncpg.exceptions import UniqueViolationError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.restaurant import Restaurant, UserRole
from app.models.table import Table
from app.models.menu import Category, MenuItem, DietType
from app.models.session import Session, SessionMember, SessionStatus, MemberRole, MemberStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.name_change_request import NameChangeRequest, NameChangeStatus
from app.core.config import settings


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

RESTAURANTS = [
    {
        "name": "Bukhara Heritage Kitchen",
        "slug": "bukhara-heritage-kitchen",
        "address": "12, Prithviraj Road, New Delhi, 110011",
        "phone": "+911123388888",
        "logo_url": None,
        "config": {"currency": "INR", "tax_percent": 5.0},
    },
    {
        "name": "Thalassa Coastal Bistro",
        "slug": "thalassa-coastal-bistro",
        "address": "7, Marine Drive, Mumbai, 400002",
        "phone": "+912222345678",
        "logo_url": None,
        "config": {"currency": "INR", "tax_percent": 5.0},
    },
    {
        "name": "Saffron & Spice Garden",
        "slug": "saffron-spice-garden",
        "address": "34, MG Road, Bengaluru, 560001",
        "phone": "+918022334455",
        "logo_url": None,
        "config": {"currency": "INR", "tax_percent": 5.0},
    },
]

# phone -> (display_name, role, restaurant_slug | None for SUPER_ADMIN)
USERS = [
    # Super admin (seeded by app startup too, duplicated phone check is safe)
    # ("+919829778167", "Super Admin", "SUPER_ADMIN", None),
    # Restaurant admins
    ("+919811001001", "Arjun Mehta", "RESTAURANT_ADMIN", "bukhara-heritage-kitchen"),
    ("+919822002002", "Priya Nair", "RESTAURANT_ADMIN", "thalassa-coastal-bistro"),
    ("+919833003003", "Rohan Sharma", "RESTAURANT_ADMIN", "saffron-spice-garden"),
    # Waiters
    ("+919844004004", "Deepak Rao", "WAITER", "bukhara-heritage-kitchen"),
    ("+919855005005", "Sunita Pillai", "WAITER", "bukhara-heritage-kitchen"),
    ("+919866006006", "Karan Patel", "WAITER", "thalassa-coastal-bistro"),
    ("+919877007007", "Megha Iyer", "WAITER", "saffron-spice-garden"),
    # Table hosts / guests (used in session seeds)
    ("+919888008008", "Aditya Verma", "TABLE_HOST", "bukhara-heritage-kitchen"),
    ("+919899009009", "Sneha Kapoor", "TABLE_GUEST", "bukhara-heritage-kitchen"),
    ("+919800010010", "Ravi Kumar", "TABLE_HOST", "thalassa-coastal-bistro"),
]

# (restaurant_slug, label, capacity)
TABLES = [
    ("bukhara-heritage-kitchen", "T1", 4),
    ("bukhara-heritage-kitchen", "T2", 4),
    ("bukhara-heritage-kitchen", "T3", 6),
    ("bukhara-heritage-kitchen", "T4", 2),
    ("bukhara-heritage-kitchen", "VIP1", 8),
    ("thalassa-coastal-bistro", "A1", 4),
    ("thalassa-coastal-bistro", "A2", 4),
    ("thalassa-coastal-bistro", "A3", 6),
    ("saffron-spice-garden", "S1", 4),
    ("saffron-spice-garden", "S2", 4),
    ("saffron-spice-garden", "S3", 6),
]

# (restaurant_slug, category_name, display_order, icon)
CATEGORIES = [
    ("bukhara-heritage-kitchen", "Starters", 1, "soup"),
    ("bukhara-heritage-kitchen", "Main Course", 2, "dish"),
    ("bukhara-heritage-kitchen", "Breads", 3, "bread"),
    ("bukhara-heritage-kitchen", "Beverages", 4, "cup"),
    ("bukhara-heritage-kitchen", "Desserts", 5, "cake"),
    ("thalassa-coastal-bistro", "Appetizers", 1, "leaf"),
    ("thalassa-coastal-bistro", "Seafood Mains", 2, "fish"),
    ("thalassa-coastal-bistro", "Rice & Noodles", 3, "bowl"),
    ("thalassa-coastal-bistro", "Drinks", 4, "glass"),
    ("saffron-spice-garden", "Salads & Soups", 1, "salad"),
    ("saffron-spice-garden", "Biryani", 2, "fire"),
    ("saffron-spice-garden", "Curries", 3, "flame"),
    ("saffron-spice-garden", "Desserts", 4, "ice-cream"),
]

# (category_key=(restaurant_slug, category_name), name, desc, price, diet_type, display_order)
MENU_ITEMS = [
    # Bukhara - Starters
    ("bukhara-heritage-kitchen", "Starters", "Dal Bukhara", "Slow-cooked overnight black lentils in a tomato base", 420.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Starters", "Sikandari Raan", "Marinated whole leg of lamb, 24-hour slow roast", 1850.0, DietType.NON_VEG, 2),
    ("bukhara-heritage-kitchen", "Starters", "Murgh Malai Kebab", "Tender chicken in cream and cheese marinade", 680.0, DietType.NON_VEG, 3),
    ("bukhara-heritage-kitchen", "Starters", "Paneer Tikka Achari", "Paneer cubes marinated in pickle spices, tandoor-grilled", 520.0, DietType.VEG, 4),
    # Bukhara - Main Course
    ("bukhara-heritage-kitchen", "Main Course", "Rogan Josh", "Slow-braised Kashmiri lamb in aromatic spices", 780.0, DietType.NON_VEG, 1),
    ("bukhara-heritage-kitchen", "Main Course", "Palak Paneer", "Fresh spinach puree with cottage cheese cubes", 440.0, DietType.VEG, 2),
    ("bukhara-heritage-kitchen", "Main Course", "Butter Chicken", "Charcoal-smoked chicken in velvety tomato-butter gravy", 580.0, DietType.NON_VEG, 3),
    # Bukhara - Breads
    ("bukhara-heritage-kitchen", "Breads", "Tandoori Roti", "Whole-wheat bread baked in clay oven", 60.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Breads", "Garlic Naan", "Leavened bread topped with garlic and butter", 90.0, DietType.VEG, 2),
    # Bukhara - Beverages
    ("bukhara-heritage-kitchen", "Beverages", "Mango Lassi", "Chilled blended yoghurt with Alphonso mango", 180.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Beverages", "Masala Chai", "Spiced milk tea", 80.0, DietType.VEG, 2),
    # Bukhara - Desserts
    ("bukhara-heritage-kitchen", "Desserts", "Gulab Jamun", "Soft dumplings soaked in cardamom-rose syrup", 180.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Desserts", "Phirni", "Creamy rice pudding with saffron and pistachios", 200.0, DietType.VEG, 2),

    # Thalassa - Appetizers
    ("thalassa-coastal-bistro", "Appetizers", "Prawn Koliwada", "Crispy marinated prawns, Koli-style", 480.0, DietType.NON_VEG, 1),
    ("thalassa-coastal-bistro", "Appetizers", "Fried Calamari", "Lightly battered squid rings with sriracha aioli", 520.0, DietType.NON_VEG, 2),
    ("thalassa-coastal-bistro", "Appetizers", "Hummus & Pita", "Lebanese-style chickpea dip with warm pita", 320.0, DietType.VEGAN, 3),
    # Thalassa - Seafood Mains
    ("thalassa-coastal-bistro", "Seafood Mains", "Goan Fish Curry", "Fresh kingfish in coconut-kokum gravy", 620.0, DietType.NON_VEG, 1),
    ("thalassa-coastal-bistro", "Seafood Mains", "Lobster Thermidor", "Butter-poached lobster with brandy cream sauce", 2200.0, DietType.NON_VEG, 2),
    ("thalassa-coastal-bistro", "Seafood Mains", "Crab Masala", "Mud crab cooked with green masala paste", 980.0, DietType.NON_VEG, 3),
    # Thalassa - Rice & Noodles
    ("thalassa-coastal-bistro", "Rice & Noodles", "Seafood Biryani", "Fragrant basmati with prawn, squid, and fish", 750.0, DietType.NON_VEG, 1),
    ("thalassa-coastal-bistro", "Rice & Noodles", "Hakka Noodles - Veg", "Stir-fried egg noodles with seasonal vegetables", 320.0, DietType.VEG, 2),
    # Thalassa - Drinks
    ("thalassa-coastal-bistro", "Drinks", "Kokum Sharbat", "Tangy coastal kokum cooler", 140.0, DietType.VEGAN, 1),
    ("thalassa-coastal-bistro", "Drinks", "Sol Kadi", "Coconut milk and kokum digestive drink", 120.0, DietType.VEG, 2),

    # Saffron - Salads & Soups
    ("saffron-spice-garden", "Salads & Soups", "Tomato Shorba", "Spiced Indian-style tomato consomme", 160.0, DietType.VEGAN, 1),
    ("saffron-spice-garden", "Salads & Soups", "Sprouted Moong Salad", "Tossed lentil sprouts with lime and chaat masala", 180.0, DietType.VEGAN, 2),
    # Saffron - Biryani
    ("saffron-spice-garden", "Biryani", "Hyderabadi Dum Biryani", "Slow-cooked mutton biryani in sealed handi", 520.0, DietType.NON_VEG, 1),
    ("saffron-spice-garden", "Biryani", "Veg Dum Biryani", "Mixed vegetable dum biryani with raita", 380.0, DietType.VEG, 2),
    ("saffron-spice-garden", "Biryani", "Egg Biryani", "Spiced basmati rice layered with masala eggs", 360.0, DietType.EGGETARIAN, 3),
    # Saffron - Curries
    ("saffron-spice-garden", "Curries", "Chettinad Chicken Curry", "Fiery Chettinad-spiced chicken with kalpasi", 540.0, DietType.NON_VEG, 1),
    ("saffron-spice-garden", "Curries", "Navratan Korma", "Nine-vegetable korma in rich cashew gravy", 420.0, DietType.VEG, 2),
    # Saffron - Desserts
    ("saffron-spice-garden", "Desserts", "Double Ka Meetha", "Hyderabadi bread pudding with saffron cream", 220.0, DietType.VEG, 1),
    ("saffron-spice-garden", "Desserts", "Kulfi Falooda", "Pistachio kulfi served on vermicelli with rose syrup", 240.0, DietType.VEG, 2),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    """Return the current UTC-aware datetime."""
    return datetime.now(timezone.utc)


def ago(**kwargs) -> datetime:
    """
    Return a past UTC datetime offset by the given timedelta keyword arguments.

    :param kwargs: Keyword arguments forwarded to ``timedelta`` (e.g., ``minutes=30``).
    :returns: A timezone-aware datetime in the past.
    """
    return utcnow() - timedelta(**kwargs)


async def seed(db: AsyncSession) -> None:
    """Insert all mock data into the database within a single transaction."""

    # -----------------------------------------------------------------------
    # Restaurants
    # -----------------------------------------------------------------------
    print("Seeding restaurants...")
    restaurant_map: dict[str, Restaurant] = {}
    for r in RESTAURANTS:
        obj = Restaurant(id=uuid.uuid4(), **r, is_active=True)
        db.add(obj)
        restaurant_map[r["slug"]] = obj
    await db.flush()

    # -----------------------------------------------------------------------
    # Users + UserRoles
    # -----------------------------------------------------------------------
    print("Seeding users and roles...")
    user_map: dict[str, User] = {}  # phone -> User
    for phone, display_name, role, restaurant_slug in USERS:
        try:
            user = User(
                id=uuid.uuid4(),
                phone=phone,
                display_name=display_name,
                is_blocked=False,
                last_login_at=ago(hours=2),
            )
            db.add(user)
        except (IntegrityError, UniqueViolationError) as e:
            print(f"User {user.phone} already exists: {e}")

        user_map[phone] = user

        if role != "SUPER_ADMIN":
            restaurant = restaurant_map[restaurant_slug]
            user_role = UserRole(
                id=uuid.uuid4(),
                user_id=user.id,
                restaurant_id=restaurant.id,
                role=role,
            )
            db.add(user_role)
    await db.flush()

    # -----------------------------------------------------------------------
    # Tables
    # -----------------------------------------------------------------------
    print("Seeding tables...")
    table_map: dict[tuple[str, str], Table] = {}  # (slug, label) -> Table
    for slug, label, capacity in TABLES:
        restaurant = restaurant_map[slug]
        table = Table(
            id=uuid.uuid4(),
            restaurant_id=restaurant.id,
            label=label,
            capacity=capacity,
            is_active=True,
        )
        db.add(table)
        table_map[(slug, label)] = table
    await db.flush()

    # -----------------------------------------------------------------------
    # Categories + Menu Items
    # -----------------------------------------------------------------------
    print("Seeding menu categories and items...")
    category_map: dict[tuple[str, str], Category] = {}  # (slug, name) -> Category
    for slug, cat_name, display_order, icon in CATEGORIES:
        cat = Category(
            id=uuid.uuid4(),
            restaurant_id=restaurant_map[slug].id,
            name=cat_name,
            display_order=display_order,
            icon=icon,
            is_active=True,
        )
        db.add(cat)
        category_map[(slug, cat_name)] = cat
    await db.flush()

    for slug, cat_name, name, desc, price, diet_type, display_order in MENU_ITEMS:
        cat = category_map[(slug, cat_name)]
        item = MenuItem(
            id=uuid.uuid4(),
            category_id=cat.id,
            name=name,
            description=desc,
            price=price,
            diet_type=diet_type,
            is_available=True,
            display_order=display_order,
        )
        db.add(item)
    await db.flush()

    # -----------------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------------
    print("Seeding sessions...")

    host_bukhara = user_map["+919888008008"]  # Aditya Verma
    guest_bukhara = user_map["+919899009009"]  # Sneha Kapoor
    host_thalassa = user_map["+919800010010"]  # Ravi Kumar

    t1 = table_map[("bukhara-heritage-kitchen", "T1")]
    a1 = table_map[("thalassa-coastal-bistro", "A1")]
    t3 = table_map[("bukhara-heritage-kitchen", "T3")]

    # Active session at Bukhara T1
    session_bukhara_active = Session(
        id=uuid.uuid4(),
        table_id=t1.id,
        host_user_id=host_bukhara.id,
        status=SessionStatus.ACTIVE,
        allow_additions=True,
        started_at=ago(minutes=30),
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db.add(session_bukhara_active)

    # Completed session at Bukhara T3
    session_bukhara_completed = Session(
        id=uuid.uuid4(),
        table_id=t3.id,
        host_user_id=host_bukhara.id,
        status=SessionStatus.COMPLETED,
        allow_additions=False,
        started_at=ago(hours=3),
        expires_at=ago(hours=2),
        closed_at=ago(hours=2),
    )
    db.add(session_bukhara_completed)

    # Active session at Thalassa A1
    session_thalassa_active = Session(
        id=uuid.uuid4(),
        table_id=a1.id,
        host_user_id=host_thalassa.id,
        status=SessionStatus.IN_PROGRESS,
        allow_additions=True,
        started_at=ago(minutes=45),
        expires_at=utcnow() + timedelta(minutes=30),
    )
    db.add(session_thalassa_active)
    await db.flush()

    # Session Members
    for session, user, role, status in [
        (session_bukhara_active, host_bukhara, MemberRole.HOST, MemberStatus.APPROVED),
        (session_bukhara_active, guest_bukhara, MemberRole.GUEST, MemberStatus.APPROVED),
        (session_bukhara_completed, host_bukhara, MemberRole.HOST, MemberStatus.APPROVED),
        (session_thalassa_active, host_thalassa, MemberRole.HOST, MemberStatus.APPROVED),
    ]:
        db.add(SessionMember(
            id=uuid.uuid4(),
            session_id=session.id,
            user_id=user.id,
            role=role,
            status=status,
            joined_at=session.started_at,
        ))
    await db.flush()

    # -----------------------------------------------------------------------
    # Orders + Order Items
    # -----------------------------------------------------------------------
    print("Seeding orders...")

    # Collect some menu items by name for convenience
    all_items: dict[str, MenuItem] = {}

    async def get_item(name: str) -> MenuItem | None:
        """Look up a seeded MenuItem by name from the in-memory cache."""
        return all_items.get(name)

    # Retrieve seeded item references -- they are already flushed, gather via identity map
    from sqlalchemy import select
    result = await db.execute(select(MenuItem))
    for mi in result.scalars().all():
        all_items[mi.name] = mi

    def build_order(session: Session, submitter: User, items_with_qty: list, status: OrderStatus, minutes_ago: int) -> tuple[Order, list[OrderItem]]:
        """
        Construct an Order and its OrderItems from a list of (name, quantity) pairs.

        :param session: The Session the order belongs to.
        :param submitter: The User submitting the order.
        :param items_with_qty: List of ``(item_name, quantity)`` tuples.
        :param status: Initial OrderStatus for the order.
        :param minutes_ago: How many minutes in the past the order was submitted.
        :returns: Tuple of the Order instance and a list of OrderItem instances.
        """
        submitted = ago(minutes=minutes_ago)
        total = sum(all_items[n].price * q for n, q in items_with_qty if n in all_items)
        order = Order(
            id=uuid.uuid4(),
            session_id=session.id,
            status=status,
            submitted_by=submitter.id,
            submitted_at=submitted,
            total_amount=total,
        )
        order_items = [
            OrderItem(
                id=uuid.uuid4(),
                order_id=order.id,
                menu_item_id=all_items[n].id,
                added_by=submitter.id,
                quantity=q,
                unit_price=all_items[n].price,
            )
            for n, q in items_with_qty if n in all_items
        ]
        return order, order_items

    orders_data = [
        # Active session at Bukhara
        (session_bukhara_active, host_bukhara,
         [("Dal Bukhara", 1), ("Murgh Malai Kebab", 2), ("Tandoori Roti", 4)],
         OrderStatus.PREPARING, 20),
        (session_bukhara_active, guest_bukhara,
         [("Mango Lassi", 2), ("Gulab Jamun", 2)],
         OrderStatus.RECEIVED, 5),
        # Completed session at Bukhara
        (session_bukhara_completed, host_bukhara,
         [("Rogan Josh", 2), ("Palak Paneer", 1), ("Garlic Naan", 4), ("Masala Chai", 2)],
         OrderStatus.COMPLETED, 180),
        # Active session at Thalassa
        (session_thalassa_active, host_thalassa,
         [("Prawn Koliwada", 2), ("Goan Fish Curry", 1), ("Seafood Biryani", 2)],
         OrderStatus.SERVED, 30),
        (session_thalassa_active, host_thalassa,
         [("Kokum Sharbat", 3)],
         OrderStatus.READY, 10),
    ]

    for session, submitter, items_with_qty, status, minutes_ago in orders_data:
        order, items = build_order(session, submitter, items_with_qty, status, minutes_ago)
        db.add(order)
        for oi in items:
            db.add(oi)

    await db.flush()

    # -----------------------------------------------------------------------
    # Name Change Requests
    # -----------------------------------------------------------------------
    print("Seeding name change requests...")
    waiter_deepak = user_map["+919844004004"]
    bukhara = restaurant_map["bukhara-heritage-kitchen"]

    db.add(NameChangeRequest(
        id=uuid.uuid4(),
        user_id=waiter_deepak.id,
        restaurant_id=bukhara.id,
        requested_name="Deepak Kumar Rao",
        status=NameChangeStatus.PENDING,
    ))
    await db.flush()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    """
    Entrypoint: initialise the async engine from DATABASE_URL and run the seeder.
    Commits all data in a single transaction and disposes the engine on completion.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await seed(db)

    await engine.dispose()
    print("\nMock database seeded successfully.")


if __name__ == "__main__":
    asyncio.run(main())
