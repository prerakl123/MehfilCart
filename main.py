"""Uvicorn entry point for the MehfilCart API server."""

import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
