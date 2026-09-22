from fastapi import APIRouter

from app.api.routes.analysis import router as analysis_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.remediation import router as remediation_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(ingestion_router)
api_router.include_router(analysis_router)
api_router.include_router(remediation_router)