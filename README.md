# MehfilCart — Backend API

Backend API for **MehfilCart**, a collaborative restaurant ordering platform. It is the single
source of truth for business logic, data persistence, authorization, and real-time event
broadcasting. The service exposes a versioned REST API under `/api/v1/` plus a WebSocket
endpoint, and is consumed by the Next.js frontend [`MehfilCartUI`](../../JavaScriptProjects/MehfilCartUI).

Guests scan a table QR code, join a shared **session**, build a collaborative **cart**, place
**orders**, and raise **service actions** (e.g. call a waiter) — all updated live over WebSocket.
Restaurant staff and admins manage menus, tables, orders, and staff via role-scoped endpoints.

> For a deep dive into design and layering, see [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md).

---

## Tech Stack

| Category        | Technology                                  |
|-----------------|---------------------------------------------|
| Framework       | FastAPI (async)                             |
| Runtime         | Python **3.11+**                            |
| ASGI server     | Uvicorn (`[standard]`)                      |
| ORM             | SQLAlchemy 2.0 (async) + asyncpg            |
| Migrations      | Alembic                                     |
| Validation      | Pydantic v2 / pydantic-settings             |
| Database        | PostgreSQL                                  |
| Cache / pub-sub | Redis (`redis[hiredis]`) — OTP, rate limits |
| Auth            | JWT (`python-jose`), `passlib` + `bcrypt`   |
| QR codes        | `qrcode[pil]`                               |
| Package manager | [`uv`](https://docs.astral.sh/uv/)          |

---

## Requirements

- **Python 3.11+** (pinned via `.python-version`; `uv` will fetch it if missing)
- **[`uv`](https://docs.astral.sh/uv/)** — package & environment manager
- **PostgreSQL** reachable at the configured `DATABASE_URL` (default `localhost:5432`, database `mehfilcart`)
- **Redis** reachable at the configured `REDIS_URL` (default `localhost:6379`)

Python dependencies are declared in [`pyproject.toml`](pyproject.toml) and locked in `uv.lock`.

---

## Setup

### 1. Install Python dependencies

```bash
uv sync
```

This creates `.venv/` and installs the exact locked dependency set.

### 2. Start PostgreSQL and Redis

The app connects to a Postgres database named **`mehfilcart`** and a Redis instance. Any local
install works; the quickest path is Docker:

```bash
# PostgreSQL — auto-creates the `mehfilcart` database
docker run -d --name mehfilcart-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=mehfilcart \
  -p 5432:5432 \
  postgres:16

# Redis
docker run -d --name mehfilcart-redis \
  -p 6379:6379 \
  redis:7
```

> Re-running later: `docker start mehfilcart-postgres mehfilcart-redis`.

The defaults in [`app/core/config.py`](app/core/config.py) match the credentials above, so **no
`.env` file is required for local development**. To override anything, create a `.env` at the
project root (see [Configuration](#configuration)).

### 3. (Optional) Apply migrations

On startup the app auto-creates tables via `Base.metadata.create_all`, which is sufficient for
local dev. To use the managed migration history instead:

```bash
uv run alembic upgrade head
```

---

## Running

```bash
uv run main.py
```

The server starts on `http://0.0.0.0:8000`. On first startup it creates the database tables and
seeds a **super admin** user (phone from `SUPER_ADMIN_PHONE`, default `+919829778167`).

| Resource          | URL                                      |
|-------------------|------------------------------------------|
| API base          | `http://localhost:8000/api/v1`           |
| Swagger UI        | `http://localhost:8000/docs`             |
| ReDoc             | `http://localhost:8000/redoc`            |
| WebSocket         | `ws://localhost:8000/api/v1/ws`          |
| Health check      | `http://localhost:8000/health`           |

---

## Configuration

Settings are loaded from environment variables / a `.env` file via `pydantic-settings`
([`app/core/config.py`](app/core/config.py)). Key variables:

| Variable                  | Default                                                                 | Purpose                                  |
|---------------------------|-------------------------------------------------------------------------|------------------------------------------|
| `APP_HOST` / `APP_PORT`   | `0.0.0.0` / `8000`                                                       | Bind address                             |
| `DEBUG`                   | `false`                                                                 | Enables Uvicorn auto-reload              |
| `DATABASE_URL`            | `postgresql+asyncpg://postgres:postgres@localhost:5432/mehfilcart`      | Async Postgres DSN                       |
| `REDIS_URL`               | `redis://localhost:6379/0`                                              | Redis connection                         |
| `JWT_SECRET_KEY`          | `dev-secret-key-change-in-production`                                   | **Change in production**                 |
| `OTP_PROVIDER`            | `console`                                                               | `console` (dev), `msg91`, or `twilio`    |
| `CORS_ALLOWED_ORIGINS`    | `["http://localhost:3000", "http://127.0.0.1:3000"]`                    | Frontend origins (see note below)        |
| `SUPER_ADMIN_PHONE`       | `+919829778167`                                                         | Seeded super admin                       |

> **CORS note:** the API sends credentials, so `CORS_ALLOWED_ORIGINS` must list **explicit
> origins** — it cannot be `"*"`. Browsers reject `Access-Control-Allow-Origin: *` on credentialed
> requests. The defaults cover the `MehfilCartUI` dev server (`http://localhost:3000`); add your
> production frontend origin here when deploying.

> **OTP in dev:** with `OTP_PROVIDER=console`, generated OTPs are printed to the server log rather
> than sent via SMS — check the console output when testing the login flow.

---

## Project Structure

```
MehfilCart/
├── main.py                  # Uvicorn entry point
├── pyproject.toml           # Dependencies & project metadata
├── uv.lock                  # Locked dependency versions
├── alembic.ini              # Alembic configuration
├── alembic/                 # Migration environment & versions
├── docs/
│   └── BACKEND_ARCHITECTURE.md
├── standalone_scripts/      # Dev/maintenance scripts (mock data, reset)
└── app/
    ├── __init__.py          # FastAPI app: lifespan, CORS, handlers, routers
    ├── core/                # config, database, redis, security, permissions, deps
    ├── models/              # SQLAlchemy ORM models
    ├── schemas/             # Pydantic request/response schemas
    ├── routers/             # API endpoints (see below)
    ├── services/            # Business-logic layer
    ├── websocket/           # Connection manager, handlers, events
    └── utils/               # OTP, phone, QR helpers
```

### API surface (under `/api/v1`)

`auth` · `sessions` · `sessions/{id}/cart` · `orders` · `menu` · `service-actions` ·
`users` · `admin` · `private` — full, interactive reference at `/docs`.

---

## Maintenance scripts

Run from the project root (these require Postgres/Redis running and load `.env` if present):

```bash
# Populate the database with mock data for local development
uv run python standalone_scripts/create_mock_data.py

# Clear all data except the super admin user (FK-safe ordering)
uv run python standalone_scripts/clear_mock_data.py
```

---

## Notes & Constraints

- **Python 3.11+ is required** — the codebase uses modern typing (`list[str]`, `X | None`).
- The database named in `DATABASE_URL` **must exist** before startup; the app creates *tables*,
  not the database itself.
- Tables are auto-created on startup for convenience; Alembic remains the source of truth for
  schema changes in shared/production environments.
- Set a strong `JWT_SECRET_KEY` and a real `OTP_PROVIDER` before deploying.
