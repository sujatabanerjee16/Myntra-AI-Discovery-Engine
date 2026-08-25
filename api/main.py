"""FastAPI application entrypoint.

Exposes health, storage, retrieval, insights, and grounded assistant routes.
Serves the built React dashboard from ``web/dist`` when present.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import assistant, health, ingestion, insights, internal, observability, retrieval, storage
from common.config import get_settings

settings = get_settings()
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Powered Wishlist Conversion Discovery Engine",
)

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not _cors_origins or _cors_origins == ["*"]:
    _cors_origins = ["*"]
_allow_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(storage.router)
app.include_router(retrieval.router)
app.include_router(insights.router)
app.include_router(assistant.router)
app.include_router(ingestion.router)
app.include_router(internal.router)
app.include_router(observability.router)


@app.get("/api/meta")
def api_meta() -> dict[str, str]:
    """API metadata (dashboard is served at ``/`` when ``web/dist`` exists)."""
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/" if WEB_DIST.is_dir() else "run `cd web && npm run dev`",
    }


_RESERVED_PATH_PREFIXES = {
    "api",
    "analytics",
    "assistant",
    "assets",
    "docs",
    "health",
    "ingestion",
    "internal",
    "insights",
    "observability",
    "openapi.json",
    "redoc",
    "retrieval",
    "storage",
}


def _mount_dashboard() -> None:
    """Serve the production-built dashboard alongside the API on port 8000."""
    if not WEB_DIST.is_dir():
        return

    assets_dir = WEB_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

    index_file = WEB_DIST / "index.html"

    @app.get("/", include_in_schema=False)
    def dashboard_root() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{page_path:path}", include_in_schema=False)
    def dashboard_spa(page_path: str) -> FileResponse:
        first_segment = page_path.split("/", 1)[0]
        if first_segment in _RESERVED_PATH_PREFIXES:
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        candidate = WEB_DIST / page_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


_mount_dashboard()
