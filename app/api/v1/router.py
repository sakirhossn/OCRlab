"""V1 API Router aggregation."""

from fastapi import APIRouter
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.usage import router as usage_router
from app.api.v1.webhooks import router as webhooks_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(documents_router)
v1_router.include_router(jobs_router)
v1_router.include_router(api_keys_router)
v1_router.include_router(webhooks_router)
v1_router.include_router(usage_router)
v1_router.include_router(health_router)
