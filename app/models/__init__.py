"""
Model registry -- import all models here so SQLAlchemy and Alembic discover them.
"""

from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin  # noqa: F401
from app.models.menu import Category, MenuItem, DietType  # noqa: F401
from app.models.order import Order, OrderItem, OrderStatus  # noqa: F401
from app.models.restaurant import Restaurant, UserRole  # noqa: F401
from app.models.session import Session, SessionMember, SessionStatus, MemberRole, MemberStatus  # noqa: F401
from app.models.table import Table  # noqa: F401
from app.models.user import User  # noqa: F401
