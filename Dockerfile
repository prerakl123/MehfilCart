# syntax=docker/dockerfile:1
# MehfilCart API -- FastAPI on Python 3.11, managed by uv.
FROM python:3.11-slim

# Bring in uv (fast, reproducible Python package manager).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy the application source.
COPY . .
RUN uv sync --frozen

EXPOSE 8000

# Dev server with autoreload. On startup the app enables the PostGIS extension
# and creates all tables (see app/__init__.py lifespan).
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
