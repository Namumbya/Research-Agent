from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from research_agent.api.deps import require_api_key
from research_agent.db.models import RunStatus
from research_agent.db.session import get_db_session
from research_agent.schemas.research import (
    ResearchBriefCreate,
    RunCreateResponse,
    RunProgress,
    RunResultResponse,
    RunStatusResponse,
    SourceOut,
)
from research_agent.services.research import create_run, execute_research_run, get_run

router = APIRouter(prefix="/v1/research", tags=["research"])


@router.post("/runs", response_model=RunCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_research_run(
    payload: ResearchBriefCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(require_api_key),
) -> RunCreateResponse:
    run = await create_run(session, payload, created_by="api-key")
    background_tasks.add_task(execute_research_run, run.id)
    return RunCreateResponse(run_id=run.id, status=run.status, created_at=run.created_at)


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_research_run_status(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: str = Depends(require_api_key),
) -> RunStatusResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "Run not found",
                    "details": {},
                }
            },
        )

    progress = None
    if isinstance(run.plan, dict):
        steps = run.plan.get("steps") or []
        done = sum(1 for step in steps if step.get("status") == "done")
        progress = RunProgress(
            current_node=None,
            tool_calls=done,
            evidence_count=len(run.sources or []),
        )

    return RunStatusResponse(
        run_id=run.id,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        progress=progress,
    )


@router.get("/runs/{run_id}/result", response_model=RunResultResponse)
async def get_research_run_result(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    _: str = Depends(require_api_key),
) -> RunResultResponse:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "Run not found",
                    "details": {},
                }
            },
        )

    if run.status != RunStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "not_ready",
                    "message": f"Run status is {run.status}",
                    "details": {"status": run.status},
                }
            },
        )

    if run.report is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "not_ready",
                    "message": "Report not available",
                    "details": {},
                }
            },
        )

    return RunResultResponse(
        run_id=run.id,
        status=run.status,
        report=run.report.report_json,
        report_markdown=run.report.report_markdown,
        sources=[
            SourceOut(id=source.id, url=source.url, title=source.title)
            for source in run.sources
        ],
    )


@router.post("/runs/{run_id}/resume", response_model=RunStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def resume_research_run(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
    _: str = Depends(require_api_key),
) -> RunStatusResponse:
    """Continue a failed or interrupted run from its LangGraph checkpoint."""
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "not_found",
                    "message": "Run not found",
                    "details": {},
                }
            },
        )

    if run.status == RunStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "already_completed",
                    "message": "Run already completed",
                    "details": {},
                }
            },
        )

    if run.status == RunStatus.running.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "already_running",
                    "message": "Run is already running",
                    "details": {},
                }
            },
        )

    background_tasks.add_task(execute_research_run, run.id, resume=True)
    return RunStatusResponse(
        run_id=run.id,
        status=RunStatus.queued.value,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=None,
        progress=None,
    )
