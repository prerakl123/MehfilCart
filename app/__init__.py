"""
MehfilCart API -- FastAPI application entry point.

Registers: CORS middleware, global exception handlers, all API routers.
Auto-creates database tables and seeds the super admin on startup.
"""

from fastapi import Response
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.database import engine, Base
from app.core.exceptions import MehfilCartException
from app.core.permissions import Role
from app.models import *  # noqa: F401, F403
from app.models.restaurant import Restaurant, UserRole
from app.models.user import User
from app.routers import all_routers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Startup/shutdown lifecycle: create tables and seed super admin."""
    await _init_database()

    # Seed a super admin user if none exists
    await _seed_super_admin()

    yield  # Application is running

    # Shutdown: dispose the engine
    await engine.dispose()
    logger.info("Database engine disposed.")


async def _init_database(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    """
    Enable PostGIS and create tables, retrying until the database is reachable.

    Under docker-compose the database may briefly refuse TCP connections on first
    boot (it restarts once after running its init scripts) even after its
    healthcheck passes, so we retry transient connection failures.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            # PostGIS must be enabled before create_all so the
            # restaurant_locations.geog geography column can be created.
            async with engine.begin() as conn:
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                except Exception as exc:  # noqa: BLE001 -- clear, actionable message
                    raise RuntimeError(
                        "PostGIS is required (for restaurant location features) "
                        "but is not available on the PostgreSQL server. Use a "
                        "PostGIS-enabled image (e.g. postgis/postgis:16-3.4) or "
                        "install the extension. Original error: " + str(exc)
                    ) from exc
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created.")
            return
        except (OperationalError, DBAPIError, OSError) as exc:
            last_exc = exc
            logger.warning(
                "Database not ready yet (attempt %d/%d): %s",
                attempt, max_attempts, exc.__class__.__name__,
            )
            await asyncio.sleep(delay_seconds)
    raise RuntimeError(
        f"Database did not become available after {max_attempts} attempts."
    ) from last_exc


async def _seed_super_admin():
    """Create the initial super admin user if not already present."""
    SENTINEL_RESTAURANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

    async with async_session_factory() as db:
        # Check if any super admin exists
        result = await db.execute(
            select(UserRole).where(UserRole.role == Role.SUPER_ADMIN)
        )
        if result.scalar_one_or_none() is not None:
            logger.info("Super admin already exists. Skipping seed.")
            return

        # Ensure the sentinel/placeholder restaurant exists for the super admin role
        result = await db.execute(
            select(Restaurant).where(Restaurant.id == SENTINEL_RESTAURANT_ID)
        )
        if result.scalar_one_or_none() is None:
            sentinel_restaurant = Restaurant(
                id=SENTINEL_RESTAURANT_ID,
                name="__platform__",
                slug="__platform__",
                is_active=False,
            )
            db.add(sentinel_restaurant)
            await db.flush()
            logger.info("Created sentinel restaurant for platform-wide roles.")

        # Get or create the super admin user
        phone = settings.SUPER_ADMIN_PHONE
        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(phone=phone, display_name="Super Admin")
            db.add(user)
            await db.flush()
            logger.info("Created super admin user: %s", phone)

        # Since super admin is platform-wide, we use a sentinel restaurant_id
        # The super admin can create actual restaurants after login
        admin_role = UserRole(
            user_id=user.id,
            restaurant_id=SENTINEL_RESTAURANT_ID,
            role=Role.SUPER_ADMIN,
        )
        db.add(admin_role)
        await db.commit()
        logger.info("Super admin role seeded for: %s", phone)


app = FastAPI(
    title="MehfilCart API",
    description="Backend API for MehfilCart - a collaborative restaurant ordering platform.",
    version="0.2.0",
    lifespan=lifespan,
)

# -- CORS Middleware --
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Global Exception Handlers --

@app.exception_handler(MehfilCartException)
async def mehfilcart_exception_handler(request: Request, exc: MehfilCartException):
    """Handle all application-level exceptions with structured JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with formatted field-level messages."""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"]})
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions. Log and return 500."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# -- Register Routers --
API_PREFIX = "/api/v1"
for router in all_routers:
    app.include_router(router, prefix=API_PREFIX)

# -- WebSocket Endpoint --
from app.websocket.handlers import websocket_endpoint  # noqa: E402

app.add_api_websocket_route(f"{API_PREFIX}/ws", websocket_endpoint)


for router in all_routers:
    for r in router.routes:
        if hasattr(r, "name"):
            logger.info("Registered route: %s %s -> %s", r.methods, r.path, r.name)
        if hasattr(r, "endpoint"):
            logger.debug("Route endpoint: %s", r.endpoint)
        if hasattr(r, "websocket_endpoint"):
            logger.info("Registered WebSocket route: %s -> %s", r.path, r.websocket_endpoint)


# -- Health Check --
@app.head("/", tags=["System"])
async def health_check_root_head():
    """Health check endpoint."""
    return Response(status_code=200)


@app.get("/", tags=["System"])
async def health_check_root():
    """Health check endpoint."""
    return {"status": "healthy", "version": app.version}


@app.head("/health", tags=["System"])
async def health_check_head():
    """Health check endpoint for load balancers."""
    return Response(status_code=200)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "healthy", "version": app.version}
