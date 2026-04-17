"""
Mock database seeder for MehfilCart.

Populates core tables with static data for local development.
Run from the project root:
    python standalone_scripts/mock_db_creation.py

Prerequisites:
    - PostgreSQL running locally with the 'mehfilcart' database already created
    - All Alembic migrations applied
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

USERS = [
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

MENU_ITEMS = [
    ("bukhara-heritage-kitchen", "Starters", "Dal Bukhara", "Slow-cooked overnight black lentils in a tomato base", 420.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Starters", "Sikandari Raan", "Marinated whole leg of lamb, 24-hour slow roast", 1850.0, DietType.NON_VEG, 2),
    ("bukhara-heritage-kitchen", "Starters", "Murgh Malai Kebab", "Tender chicken in cream and cheese marinade", 680.0, DietType.NON_VEG, 3),
    ("bukhara-heritage-kitchen", "Starters", "Paneer Tikka Achari", "Paneer cubes marinated in pickle spices, tandoor-grilled", 520.0, DietType.VEG, 4),
    ("bukhara-heritage-kitchen", "Main Course", "Rogan Josh", "Slow-braised Kashmiri lamb in aromatic spices", 780.0, DietType.NON_VEG, 1),
    ("bukhara-heritage-kitchen", "Main Course", "Palak Paneer", "Fresh spinach puree with cottage cheese cubes", 440.0, DietType.VEG, 2),
    ("bukhara-heritage-kitchen", "Main Course", "Butter Chicken", "Charcoal-smoked chicken in velvety tomato-butter gravy", 580.0, DietType.NON_VEG, 3),
    ("bukhara-heritage-kitchen", "Breads", "Tandoori Roti", "Whole-wheat bread baked in clay oven", 60.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Breads", "Garlic Naan", "Leavened bread topped with garlic and butter", 90.0, DietType.VEG, 2),
    ("bukhara-heritage-kitchen", "Beverages", "Mango Lassi", "Chilled blended yoghurt with Alphonso mango", 180.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Beverages", "Masala Chai", "Spiced milk tea", 80.0, DietType.VEG, 2),
    ("bukhara-heritage-kitchen", "Desserts", "Gulab Jamun", "Soft dumplings soaked in cardamom-rose syrup", 180.0, DietType.VEG, 1),
    ("bukhara-heritage-kitchen", "Desserts", "Phirni", "Creamy rice pudding with saffron and pistachios", 200.0, DietType.VEG, 2),
    ("thalassa-coastal-bistro", "Appetizers", "Prawn Koliwada", "Crispy marinated prawns, Koli-style", 480.0, DietType.NON_VEG, 1),
    ("thalassa-coastal-bistro", "Appetizers", "Fried Calamari", "Lightly battered squid rings with sriracha aioli", 520.0, DietType.NON_VEG, 2),
    ("thalassa-coastal-bistro", "Appetizers", "Hummus & Pita", "Lebanese-style chickpea dip with warm pita", 320.0, DietType.VEGAN, 3),
    ("thalassa-coastal-bistro", "Seafood Mains", "Goan Fish Curry", "Fresh kingfish in coconut-kokum gravy", 620.0, DietType.NON_VEG, 1),
    ("thalassa-coastal-bistro", "Seafood Mains", "Lobster Thermidor", "Butter-poached lobster with brandy cream sauce", 2200.0, DietType.NON_VEG, 2),
    ("thalassa-coastal-bistro", "Seafood Mains", "Crab Masala", "Mud crab cooked with green masala paste", 980.0, DietType.NON_VEG, 3),
    ("thalassa-coastal-bistro", "Rice & Noodles", "Seafood Biryani", "Fragrant basmati with prawn, squid, and fish", 750.0, DietType.NON_VEG, 1),
    ("thalassa-coastal-bistro", "Rice & Noodles", "Hakka Noodles - Veg", "Stir-fried egg noodles with seasonal vegetables", 320.0, DietType.VEG, 2),
    ("thalassa-coastal-bistro", "Drinks", "Kokum Sharbat", "Tangy coastal kokum cooler", 140.0, DietType.VEGAN, 1),
    ("thalassa-coastal-bistro", "Drinks", "Sol Kadi", "Coconut milk and kokum digestive drink", 120.0, DietType.VEG, 2),
    ("saffron-spice-garden", "Salads & Soups", "Tomato Shorba", "Spiced Indian-style tomato consomme", 160.0, DietType.VEGAN, 1),
    ("saffron-spice-garden", "Salads & Soups", "Sprouted Moong Salad", "Tossed lentil sprouts with lime and chaat masala", 180.0, DietType.VEGAN, 2),
    ("saffron-spice-garden", "Biryani", "Hyderabadi Dum Biryani", "Slow-cooked mutton biryani in sealed handi", 520.0, DietType.NON_VEG, 1),
    ("saffron-spice-garden", "Biryani", "Veg Dum Biryani", "Mixed vegetable dum biryani with raita", 380.0, DietType.VEG, 2),
    ("saffron-spice-garden", "Biryani", "Egg Biryani", "Spiced basmati rice layered with masala eggs", 360.0, DietType.EGGETARIAN, 3),
    ("saffron-spice-garden", "Curries", "Chettinad Chicken Curry", "Fiery Chettinad-spiced chicken with kalpasi", 540.0, DietType.NON_VEG, 1),
    ("saffron-spice-garden", "Curries", "Navratan Korma", "Nine-vegetable korma in rich cashew gravy", 420.0, DietType.VEG, 2),
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
    """
    return utcnow() - timedelta(**kwargs)


async def seed(db: AsyncSession) -> None:
    """Insert static core mock data into the database within a single transaction."""

    print("Seeding restaurants...")
    restaurant_map: dict[str, Restaurant] = {}
    for r in RESTAURANTS:
        obj = Restaurant(id=uuid.uuid4(), **r, is_active=True)
        db.add(obj)
        restaurant_map[r["slug"]] = obj
    await db.flush()

    print("Seeding users and roles...")
    user_map: dict[str, User] = {}
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
            print(f"User {phone} already exists: {e}")

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

    print("Seeding tables...")
    table_map: dict[tuple[str, str], Table] = {}
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

    print("Seeding menu categories and items...")
    category_map: dict[tuple[str, str], Category] = {}
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


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main() -> None:
    """
    Entrypoint: initialise the async engine from DATABASE_URL and run the seeder.
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
    print("\nMock core database seeded successfully (no live data).")


if __name__ == "__main__":
    asyncio.run(main())
