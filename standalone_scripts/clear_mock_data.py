"""
Database closer script for MehfilCart.

Clears completely the mock database except the super admin user.
It follows the correct sequence of relational model table deletions
to avoid Foreign Key constraint violations.
"""

import asyncio
import os
import sys

# Allow importing the app package from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.restaurant import Restaurant, UserRole
from app.models.table import Table
from app.models.menu import Category, MenuItem
from app.models.session import Session, SessionMember
from app.models.order import Order, OrderItem
from app.models.name_change_request import NameChangeRequest
from app.core.config import settings

async def clear_data(db: AsyncSession) -> None:
    """Remove data systematically to respect relational tables' strict constraints."""
    
    print("Clearing NameChangeRequest...")
    await db.execute(delete(NameChangeRequest))
    
    print("Clearing OrderItem...")
    await db.execute(delete(OrderItem))
    
    print("Clearing Order...")
    await db.execute(delete(Order))
    
    print("Clearing SessionMember...")
    await db.execute(delete(SessionMember))
    
    print("Clearing Session...")
    await db.execute(delete(Session))
    
    print("Clearing MenuItem...")
    await db.execute(delete(MenuItem))
    
    print("Clearing Category...")
    await db.execute(delete(Category))
    
    print("Clearing Table...")
    await db.execute(delete(Table))

    print("Clearing UserRole...")
    await db.execute(delete(UserRole))
    
    print("Clearing Restaurant...")
    await db.execute(delete(Restaurant))
    
    # We do not delete super admin
    print(f"Clearing User (except super admin: {settings.SUPER_ADMIN_PHONE})...")
    await db.execute(delete(User).where(User.phone != settings.SUPER_ADMIN_PHONE))

async def main() -> None:
    """Entry point invoking clearing context within a transaction boundary."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await clear_data(db)

    await engine.dispose()
    print("\nDatabase cleared successfully except for super admin.")

if __name__ == "__main__":
    asyncio.run(main())
