"""FastAPI application entrypoint.

Exposes health, storage, retrieval, insights, and grounded assistant routes.
Serves the built React dashboard from ``web/dist`` when present.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import (
    assistant,
    health,
    ingestion,
    insights,
    internal,
    observability,
    retrieval,
    storage,
)
from common.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm offline conversion metrics when serving the JSON/demo backend."""
    try:
        from api import backend

        if backend.use_json_backend():
            from internal.offline import run_offline_internal_pipeline

            result = run_offline_internal_pipeline()
            logger.info(
                "Offline conversion warmed at startup run_version=%s",
                result.run_version,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to warm offline internal pipeline at startup")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-Powered Wishlist Conversion Discovery Engine",
    lifespan=lifespan,
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

_API_ROUTERS = (
    health.router,
    storage.router,
    retrieval.router,
    insights.router,
    assistant.router,
    ingestion.router,
    internal.router,
    observability.router,
)
for _router in _API_ROUTERS:
    app.include_router(_router)
    # Same-origin Vite/Vercel builds call /api/insights/...; FastAPI routes are bare.
    app.include_router(_router, prefix="/api", include_in_schema=False)


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
