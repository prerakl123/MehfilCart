"""Router registry -- import all routers for app registration."""

from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.cart import router as cart_router
from app.routers.menu import router as menu_router
from app.routers.orders import router as orders_router
from app.routers.sessions import router as sessions_router
from app.routers.user import router as user_router
from app.routers.private import router as private_router
from app.routers.service_actions import router as service_actions_router


all_routers = [
    auth_router,
    sessions_router,
    cart_router,
    orders_router,
    menu_router,
    admin_router,
    user_router,
    private_router,
    service_actions_router,
]
