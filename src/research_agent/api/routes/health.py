from fastapi import APIRouter, Response, status

from research_agent.db.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    db_ok = await check_database()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "error"}
    return {"status": "ready", "database": "ok"}
