from fastapi import APIRouter

from research_agent.api.routes.health import router as health_router
from research_agent.api.routes.research import router as research_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(research_router)
