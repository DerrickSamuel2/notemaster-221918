import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import router as notes_router
from src.api.routers import tags_router
from src.db.init_db import init_db
from src.db.session import engine

openapi_tags = [
    {"name": "health", "description": "Service health and diagnostics."},
    {"name": "notes", "description": "Create, read, update, delete, list and search notes."},
    {"name": "tags", "description": "List and manage tags."},
]

app = FastAPI(
    title=os.getenv("APP_TITLE", "NoteMaster API"),
    description=os.getenv(
        "APP_DESCRIPTION",
        "Backend API for a notes application with tagging, search, and pagination.",
    ),
    version=os.getenv("APP_VERSION", "0.1.0"),
    openapi_tags=openapi_tags,
)


def _cors_origins() -> list[str]:
    """Parse CORS origins from environment.

    Supports:
      - CORS_ALLOW_ORIGINS="*"
      - CORS_ALLOW_ORIGINS="http://localhost:3000,https://example.com"
    """
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    """Initialize database schema on startup (lightweight, migrations-less)."""
    init_db(engine)


@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Simple health check endpoint.",
    operation_id="health_check",
)
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}


app.include_router(notes_router)
app.include_router(tags_router)
