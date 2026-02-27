# MehfilCart -- Backend Architecture

> **Repository:** `MehfilCart`
> **Version:** 0.2.0-draft
> **Last Updated:** 2026-02-21
> **Status:** Planning Phase

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Application Layers](#4-application-layers)
5. [Database Models and ORM](#5-database-models-and-orm)
6. [API Router Design](#6-api-router-design)
7. [Authentication and Authorization](#7-authentication-and-authorization)
8. [Real-time (WebSocket) Layer](#8-real-time-websocket-layer)
9. [Service Layer](#9-service-layer)
10. [Configuration and Environment](#10-configuration-and-environment)
11. [Error Handling](#11-error-handling)
12. [Dependency Management](#12-dependency-management)
13. [Testing Strategy](#13-testing-strategy)
14. [Backend-Specific Roadmap](#14-backend-specific-roadmap)

---

## 1. Overview

The MehfilCart backend is a **FastAPI** application serving as the single source of truth for
all business logic, data persistence, authorization, and real-time event broadcasting. It
exposes a versioned REST API (`/api/v1/`) consumed by the Next.js frontend (`MehfilCartUI`).

### Responsibility Boundary

| Concern                               | Backend  | Frontend |
|----------------------------------------|:--------:|:--------:|
| Business logic and rules enforcement   | Yes      | --       |
| Authorization (role + resource checks) | Yes      | --       |
| Data persistence (PostgreSQL)          | Yes      | --       |
| OTP generation, storage, validation    | Yes      | --       |
| JWT issuance, validation, rotation     | Yes      | --       |
| Session lifecycle management           | Yes      | --       |
| Session timeout/expiry enforcement     | Yes      | --       |
| Real-time event broadcasting           | Yes      | --       |
| Input validation (Pydantic schemas)    | Yes      | Partial  |
| API response formatting                | Yes      | --       |
| Rate limiting                          | Yes      | --       |
| File/image storage management          | Yes      | --       |

---

## 2. Technology Stack

| Category           | Technology                      | Notes                                          |
|--------------------|---------------------------------|------------------------------------------------|
| Framework          | FastAPI                         | Async-first, auto OpenAPI/Swagger docs         |
| Runtime            | Python 3.11+                    | Type hints, `asyncio` native                   |
| ASGI Server        | Uvicorn                         | High-performance async server                  |
| ORM                | SQLAlchemy 2.0 (async)          | Declarative models, relationship mapping       |
| Migrations         | Alembic                         | Schema versioning and migrations               |
| Validation         | Pydantic v2                     | Request/response schemas (built into FastAPI)   |
| Database           | PostgreSQL                      | Primary relational store                       |
| Cache              | Redis (via `redis-py` async)    | OTP storage, session cache, pub/sub            |
| Auth               | PyJWT / python-jose             | JWT creation, validation (RS256)               |
| OTP Delivery       | MSG91 / Twilio SDK              | SMS OTP sending                                |
| WebSocket          | FastAPI WebSocket / Socket.IO   | Real-time bidirectional communication          |
| Task Queue         | (Future) Celery / ARQ           | Background tasks (session expiry, notifications)|
| Package Manager    | uv                              | Fast Python package manager                    |
| Testing            | pytest + pytest-asyncio + httpx | Async test suite                               |

---

## 3. Project Structure

The existing skeleton has the foundation. The target structure expands on it:

```
MehfilCart/
|-- docs/
|   +-- BACKEND_ARCHITECTURE.md       # This document
|
|-- app/
|   |-- __init__.py                    # FastAPI app instance creation
|   |
|   |-- routers/                       # API route handlers (thin controllers)
|   |   |-- __init__.py                # Router registration
|   |   |-- auth.py                    # POST /auth/request-otp, /auth/verify-otp, etc.
|   |   |-- sessions.py               # Session CRUD, join, reopen
|   |   |-- cart.py                    # Cart item CRUD within a session
|   |   |-- orders.py                 # Order submission, status updates, cancel
|   |   |-- menu.py                   # Menu and category read/write
|   |   |-- admin.py                  # Admin dashboard, table mgmt, staff mgmt, config
|   |   +-- payments.py               # (Future) Payment integration
|   |
|   |-- models/                        # SQLAlchemy ORM models
|   |   |-- __init__.py
|   |   |-- user.py                    # User model
|   |   |-- restaurant.py             # Restaurant model
|   |   |-- table.py                  # Table model
|   |   |-- session.py                # Session, SessionMember models
|   |   |-- menu.py                   # Category, MenuItem models
|   |   |-- order.py                  # Order, OrderItem models
|   |   +-- base.py                   # Declarative base, common mixins (UUID PK, timestamps)
|   |
|   |-- schemas/                       # Pydantic request/response schemas
|   |   |-- __init__.py
|   |   |-- auth.py                    # OTPRequest, OTPVerify, TokenResponse
|   |   |-- session.py                # SessionCreate, SessionResponse, MemberAction
|   |   |-- cart.py                   # CartItemCreate, CartItemUpdate, CartResponse
|   |   |-- order.py                  # OrderSubmit, OrderStatusUpdate, OrderResponse
|   |   |-- menu.py                   # CategorySchema, MenuItemSchema
|   |   +-- admin.py                  # DashboardStats, TableCreate, StaffCreate
|   |
|   |-- services/                      # Business logic layer
|   |   |-- __init__.py
|   |   |-- auth_service.py           # OTP generation, verification, JWT issuance
|   |   |-- session_service.py        # Session lifecycle, timeout, member management
|   |   |-- cart_service.py           # Cart operations, permission checks
|   |   |-- order_service.py          # Order submission, status transitions
|   |   |-- menu_service.py           # Menu CRUD logic
|   |   +-- admin_service.py          # Dashboard stats, table/staff management
|   |
|   |-- core/                          # Cross-cutting concerns
|   |   |-- __init__.py
|   |   |-- config.py                 # Settings loaded from environment variables
|   |   |-- database.py               # Async SQLAlchemy engine, session factory
|   |   |-- redis.py                  # Redis client setup
|   |   |-- security.py               # JWT creation/validation, password hashing (if needed)
|   |   |-- dependencies.py           # FastAPI dependencies (get_db, get_current_user, etc.)
|   |   |-- permissions.py            # Role and permission definitions, authorization decorators
|   |   +-- exceptions.py             # Custom exception classes
|   |
|   |-- websocket/                     # Real-time communication
|   |   |-- __init__.py
|   |   |-- manager.py                # Connection manager (rooms, broadcast)
|   |   |-- handlers.py               # Incoming event handlers
|   |   +-- events.py                 # Event type constants
|   |
|   +-- utils/                         # Utility functions
|       |-- __init__.py
|       |-- otp.py                     # OTP generation, formatting
|       |-- qr.py                      # QR code generation for tables
|       +-- phone.py                   # Phone number validation, formatting
|
|-- alembic/                           # Database migration scripts
|   |-- env.py
|   |-- script.py.mako
|   +-- versions/                      # Auto-generated migration files
|
|-- tests/                             # Test suite
|   |-- conftest.py                    # Fixtures (test DB, test client, auth helpers)
|   |-- test_auth.py
|   |-- test_sessions.py
|   |-- test_cart.py
|   |-- test_orders.py
|   |-- test_menu.py
|   +-- test_admin.py
|
|-- .env.example                       # Environment variable template
|-- .gitignore
|-- .python-version                    # Python version (3.11)
|-- alembic.ini                        # Alembic configuration
|-- config.py                          # (Current) App config -- to be moved to app/core/config.py
|-- main.py                            # Uvicorn entry point
|-- pyproject.toml                     # Project metadata and dependencies
+-- uv.lock                            # Dependency lock file
```

### Current State vs Target

| Component            | Current State               | Target State                            |
|----------------------|-----------------------------|-----------------------------------------|
| `app/__init__.py`    | FastAPI instance created    | Add middleware, exception handlers, CORS |
| `app/routers/`       | admin (1 endpoint), cart/menu/payments (empty) | Full CRUD routers per domain |
| `app/models/`        | Does not exist              | SQLAlchemy models for all entities       |
| `app/schemas/`       | Does not exist              | Pydantic schemas for all endpoints       |
| `app/services/`      | Empty directory             | Service layer with business logic        |
| `app/core/`          | Does not exist              | Config, DB, Redis, security, permissions |
| `app/websocket/`     | Does not exist              | WebSocket connection manager             |
| `app/utils/`         | Does not exist              | OTP, QR, phone utilities                 |
| `config.py`          | Basic host/port             | Move to app/core/config.py with pydantic-settings |
| `tests/`             | Does not exist              | pytest test suite                        |
| `alembic/`           | Does not exist              | Database migration setup                 |

---

## 4. Application Layers

All requests flow through clearly separated layers:

```
Client Request
      |
      v
[FastAPI Router]           -- Route matching, parameter extraction
      |
      v
[Dependencies]             -- Authentication, DB session injection, permission checks
      |
      v
[Pydantic Schema]          -- Request validation and serialization
      |
      v
[Service Layer]            -- Business logic, orchestration
      |
      v
[ORM / Database]           -- Data access, queries, mutations
      |
      v
[Response Schema]          -- Response serialization
      |
      v
Client Response
```

### Layer Rules

| Layer        | Can Access                | Cannot Access              |
|--------------|---------------------------|----------------------------|
| Router       | Dependencies, Services    | ORM models directly        |
| Service      | ORM models, Redis, Utils  | Request/Response objects    |
| Model        | Other models (relations)  | Services, Routers          |
| Schema       | Nothing (data containers) | Everything else             |
| Core         | Config, external services | Business logic              |

---

## 5. Database Models and ORM

### Base Model Mixin

All models inherit from a common base providing:
- `id`: UUID primary key (auto-generated via `uuid4`)
- `created_at`: Timestamp with timezone (auto-set)
- `updated_at`: Timestamp with timezone (auto-update)

### Model Definitions

All entities defined in the system ARCHITECTURE.md are implemented as SQLAlchemy 2.0
declarative models. Key relationships:

```
Restaurant --1:N--> Table --1:N--> Session --1:N--> SessionMember
                                           --1:N--> Order --1:N--> OrderItem
Restaurant --1:N--> Category --1:N--> MenuItem <--N:1-- OrderItem
User --1:N--> SessionMember
User --1:N--> OrderItem (added_by)
User --1:N--> Order (submitted_by)
```

### Migration Strategy

- Use **Alembic** for all schema changes.
- Never modify the database schema manually.
- Migration naming convention: `YYYYMMDD_HHMM_description.py`
- Each migration must be reversible (include `downgrade()`).

---

## 6. API Router Design

### Conventions

- All endpoints are prefixed with `/api/v1/`.
- Routers use FastAPI's `APIRouter` with `prefix` and `tags`.
- Path parameters use snake_case: `{session_id}`, `{item_id}`.
- Request bodies validated by Pydantic schemas.
- Responses return Pydantic response models (not raw ORM objects).
- HTTP status codes follow REST conventions:
  - `200` OK, `201` Created, `204` No Content
  - `400` Bad Request, `401` Unauthorized, `403` Forbidden, `404` Not Found
  - `409` Conflict, `422` Validation Error, `429` Rate Limited
  - `500` Internal Server Error

### Router Registration (in `app/__init__.py`)

```python
# All routers registered with the /api/v1 prefix
app.include_router(auth_router,     prefix="/api/v1")
app.include_router(session_router,  prefix="/api/v1")
app.include_router(cart_router,     prefix="/api/v1")
app.include_router(order_router,    prefix="/api/v1")
app.include_router(menu_router,     prefix="/api/v1")
app.include_router(admin_router,    prefix="/api/v1")
```

### Endpoint Summary

Refer to the API Contract in the system `ARCHITECTURE.md` for the complete endpoint listing.

---

## 7. Authentication and Authorization

### Authentication Flow (Backend Side)

1. **OTP Request**: Client sends phone number -> backend generates a 6-digit OTP, stores in
   Redis with a 5-minute TTL, sends via SMS provider (MSG91/Twilio).
2. **OTP Verification**: Client sends phone + OTP -> backend verifies against Redis, creates
   or fetches User record, issues JWT pair (access + refresh).
3. **Access Token**: Short-lived (30 min), signed with RS256 private key.
4. **Refresh Token**: Long-lived (7 days), stored as httpOnly cookie.
5. **Token Refresh**: Client sends refresh cookie -> backend validates, issues new access token.
6. **Logout**: Backend invalidates the refresh token (blacklist in Redis or delete).

### Authorization Enforcement

Authorization is enforced **entirely on the backend**. The frontend may hide UI elements based
on roles, but the backend never trusts the client.

#### Permission Architecture

```python
# app/core/permissions.py

ROLE_PERMISSIONS = {
    "SUPER_ADMIN": ["*"],
    "RESTAURANT_ADMIN": [
        "menu:manage", "table:manage", "session:manage",
        "order:view", "order:cancel", "order:edit",
        "staff:manage", "config:manage",
    ],
    "WAITER": ["order:view", "order:cancel", "order:status-update"],
    "TABLE_HOST": [
        "session:create", "session:manage-members",
        "cart:add", "cart:remove-any", "cart:toggle-additions",
        "order:submit", "order:view-own",
    ],
    "TABLE_GUEST": ["cart:add", "cart:remove-own", "order:view-own"],
}
```

#### Dependency-Based Authorization

FastAPI dependencies check permissions at the router level:

```python
# Example usage in a router
@router.post("/sessions/{session_id}/cart/items")
async def add_cart_item(
    session_id: UUID,
    item: CartItemCreate,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_permission("cart:add")),
    db: AsyncSession = Depends(get_db),
):
    return await cart_service.add_item(db, session_id, current_user, item)
```

---

## 8. Real-time (WebSocket) Layer

### Connection Manager

The WebSocket manager maintains:
- A registry of active connections keyed by user ID.
- Room memberships (which connections belong to which session/restaurant rooms).
- Broadcast methods to send events to specific rooms.

### Implementation Approach

```python
# app/websocket/manager.py

class ConnectionManager:
    """
    Manages active WebSocket connections and room-based broadcasting.
    """
    # active_connections: dict[str, WebSocket]   -- user_id -> connection
    # rooms: dict[str, set[str]]                 -- room_name -> set of user_ids

    async def connect(self, websocket, user_id): ...
    async def disconnect(self, user_id): ...
    async def join_room(self, user_id, room_name): ...
    async def leave_room(self, user_id, room_name): ...
    async def broadcast_to_room(self, room_name, event, payload): ...
    async def send_to_user(self, user_id, event, payload): ...
```

### Event Flow

1. Service layer performs an action (e.g., `cart_service.add_item`).
2. After the DB commit, the service calls `manager.broadcast_to_room(...)`.
3. All connected clients in that room receive the event.
4. The frontend updates its local Zustand store based on the event type.

### Room Naming Convention

| Room Pattern              | Who Joins                          |
|---------------------------|------------------------------------|
| `session:{session_id}`    | All session members (host + guests)|
| `staff:{restaurant_id}`   | All waiter/staff of the restaurant |
| `admin:{restaurant_id}`   | Admin users of the restaurant      |

---

## 9. Service Layer

### Design Principles

- Each service module corresponds to a domain (auth, session, cart, order, menu, admin).
- Services receive the database session and validated data as arguments.
- Services contain all business rules and decision logic.
- Services raise custom exceptions (caught by global exception handlers).
- Services are stateless functions (no class instances needed unless managing state).

### Service Inventory

| Service                | Key Responsibilities                                           |
|------------------------|----------------------------------------------------------------|
| `auth_service`         | Generate OTP, verify OTP, create/fetch user, issue JWTs        |
| `session_service`      | Create session, manage members, enforce timeout, reopen        |
| `cart_service`         | Add/remove/update items, check permissions, enforce session state |
| `order_service`        | Submit order from cart, transition status, cancel              |
| `menu_service`         | CRUD categories and items, toggle availability                 |
| `admin_service`        | Dashboard statistics, table CRUD, staff CRUD, config updates   |

### Example: Session Timeout Enforcement

```
When a cart operation is attempted:
  1. cart_service receives the session_id.
  2. Loads the session from DB.
  3. Checks session.status is ACTIVE (not TIMED_OUT, LOCKED, etc.).
  4. Checks session.expires_at > current time.
  5. If expired: updates status to TIMED_OUT, broadcasts event, raises 403.
  6. If valid: proceeds with the cart operation.
```

---

## 10. Configuration and Environment

### Configuration Approach

Use `pydantic-settings` (BaseSettings) to load configuration from environment variables with
type validation and defaults.

### Environment Variables

```
# Server
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mehfilcart

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_PRIVATE_KEY_PATH=/path/to/private.pem
JWT_PUBLIC_KEY_PATH=/path/to/public.pem
JWT_ACCESS_TOKEN_EXPIRY_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRY_DAYS=7

# OTP
OTP_PROVIDER=msg91               # or "twilio"
OTP_API_KEY=your-api-key
OTP_EXPIRY_SECONDS=300
OTP_MAX_ATTEMPTS=3
OTP_RATE_LIMIT_WINDOW_MINUTES=15
OTP_RATE_LIMIT_MAX=3

# Session Defaults
DEFAULT_SESSION_TIMEOUT_MINUTES=45
DEFAULT_MAX_GUESTS_PER_SESSION=8
SESSION_REOPEN_WINDOW_MINUTES=15

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

### Migration Path for Current `config.py`

The current `config.py` at the project root is a basic class with `APP_HOST` and `APP_PORT`.
This will be replaced by `app/core/config.py` using `pydantic-settings.BaseSettings`, and the
root `config.py` will be removed. The `main.py` entry point will import from `app.core.config`.

---

## 11. Error Handling

### Custom Exceptions

```python
# app/core/exceptions.py

class MehfilCartException(Exception):
    """Base exception for all app-level errors."""
    status_code: int = 500
    detail: str = "Internal server error"

class NotFoundException(MehfilCartException):
    status_code = 404

class ForbiddenException(MehfilCartException):
    status_code = 403

class ConflictException(MehfilCartException):
    status_code = 409

class RateLimitException(MehfilCartException):
    status_code = 429

class SessionExpiredException(MehfilCartException):
    status_code = 403
    detail = "Session has expired"
```

### Global Exception Handlers

Registered in `app/__init__.py`:
- `MehfilCartException` -> JSON error response with `status_code` and `detail`.
- `RequestValidationError` -> 422 with formatted field errors.
- `Exception` (fallback) -> 500 with generic message, log the full traceback.

---

## 12. Dependency Management

### Current Dependencies (from `pyproject.toml`)

```toml
dependencies = [
    "fastapi>=0.129.0",
    "uvicorn[standard]>=0.41.0",
]
```

### Planned Dependencies

| Package                  | Purpose                                  | Phase   |
|--------------------------|------------------------------------------|---------|
| `sqlalchemy[asyncio]`    | Async ORM                                | Phase 1 |
| `asyncpg`                | Async PostgreSQL driver                  | Phase 1 |
| `alembic`                | Database migrations                      | Phase 1 |
| `pydantic-settings`      | Environment-based configuration          | Phase 1 |
| `redis[hiredis]`         | Async Redis client with C parser         | Phase 1 |
| `python-jose[cryptography]` | JWT creation and validation           | Phase 1 |
| `httpx`                  | HTTP client for OTP provider and testing | Phase 1 |
| `qrcode[pil]`            | QR code generation for tables            | Phase 2 |
| `python-multipart`       | File upload handling                     | Phase 2 |
| `boto3`                  | S3 object storage (images)               | Phase 2 |
| `celery` or `arq`        | Background task queue                    | Phase 3 |
| `pytest`                 | Test framework                           | Phase 1 |
| `pytest-asyncio`         | Async test support                       | Phase 1 |

---

## 13. Testing Strategy

| Level              | Tool                    | Coverage Target                                   |
|--------------------|-------------------------|---------------------------------------------------|
| Unit tests         | pytest                  | Service functions, utility functions               |
| Integration tests  | pytest + httpx TestClient | API endpoints with test database                 |
| Database tests     | pytest + async fixtures | Model relationships, constraints, queries          |

### Test Database Strategy

- Use a separate PostgreSQL database for tests (or SQLite for fast unit tests).
- Each test function gets a fresh transaction that is rolled back after the test.
- Fixtures provide authenticated test clients for each role.

### Test Naming Convention

```
tests/
  test_auth.py
    test_request_otp_valid_phone
    test_request_otp_invalid_phone
    test_request_otp_rate_limited
    test_verify_otp_correct
    test_verify_otp_expired
    test_verify_otp_wrong_code
    ...
```

---

## 14. Backend-Specific Roadmap

### Phase 1: Foundation
- [ ] Set up `app/core/config.py` with pydantic-settings (replace root config.py)
- [ ] Set up `app/core/database.py` with async SQLAlchemy engine
- [ ] Set up `app/core/redis.py` with async Redis client
- [ ] Create `app/models/base.py` with UUID PK mixin and timestamp mixin
- [ ] Create all ORM models (User, Restaurant, Table, Session, etc.)
- [ ] Set up Alembic and run initial migration
- [ ] Create `app/core/security.py` (JWT sign/verify, token helpers)
- [ ] Create `app/core/dependencies.py` (get_db, get_current_user)
- [ ] Create `app/core/permissions.py` (role-permission map, require_permission)
- [ ] Create `app/core/exceptions.py` and register global handlers

### Phase 2: Auth and Session APIs
- [ ] Implement `auth_service` (OTP gen, verify, JWT issuance)
- [ ] Implement `auth` router (request-otp, verify-otp, refresh, logout)
- [ ] Implement `session_service` (create, join, approve, timeout, reopen)
- [ ] Implement `sessions` router (CRUD, join, reopen)
- [ ] Add CORS middleware for frontend origin

### Phase 3: Cart, Order, Menu APIs
- [ ] Implement `cart_service` (add, remove, update, permission checks)
- [ ] Implement `cart` router
- [ ] Implement `order_service` (submit, status transitions, cancel)
- [ ] Implement `orders` router
- [ ] Implement `menu_service` (category/item CRUD, availability)
- [ ] Implement `menu` router

### Phase 4: Admin, WebSocket, Background Tasks
- [ ] Implement `admin_service` (dashboard stats, table/staff CRUD, config)
- [ ] Implement `admin` router (expand existing skeleton)
- [ ] Implement WebSocket connection manager and event handlers
- [ ] Implement background session timeout checker (scheduled task)

### Phase 5: Hardening
- [ ] Rate limiting middleware
- [ ] Request logging middleware
- [ ] Comprehensive test suite
- [ ] API documentation review (OpenAPI/Swagger)
- [ ] Security audit (input sanitization, SQL injection prevention)
