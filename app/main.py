"""Unlimited OCR Cloud (ocrLab) FastAPI Application Entrypoint."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.internal.worker import router as internal_worker_router
from app.api.v1.router import v1_router
from app.config import settings
from app.core.database import init_db
from app.core.errors import AppException, app_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Initialize database tables on startup (if not already managed via migrations)
    await init_db()
    yield


app = FastAPI(
    title="Unlimited OCR Cloud API",
    description=(
        "Production-grade, multi-tenant PDF-to-structured-data API platform powered by "
        "Baidu Unlimited-OCR-2 and PyMuPDF."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:
    """Injects or propagates X-Request-ID on all incoming requests and outgoing responses."""
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = req_id

    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# Register exception handlers
app.add_exception_handler(AppException, app_exception_handler)

# Include versioned API routers
app.include_router(v1_router)
app.include_router(internal_worker_router)


# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api_v1": "/v1",
    }


@app.get("/api", include_in_schema=False)
async def api_info():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api_v1": "/v1",
    }
