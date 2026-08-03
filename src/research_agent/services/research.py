from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from research_agent.agent.graph import get_research_graph
from research_agent.core.config import get_settings
from research_agent.db.models import ResearchReport, ResearchRun, ResearchSource, RunStatus
from research_agent.db.session import AsyncSessionLocal
from research_agent.schemas.research import ResearchBriefCreate

logger = logging.getLogger(__name__)


def _brief_dict(brief: ResearchBriefCreate) -> dict[str, Any]:
    return {
        "topic": brief.topic,
        "goals": brief.goals,
        "constraints": brief.constraints,
        "audience": brief.audience,
        "depth": brief.depth.value,
        "seed_urls": [str(url) for url in brief.seed_urls],
        "metadata": brief.metadata,
    }


async def create_run(
    session: AsyncSession,
    brief: ResearchBriefCreate,
    *,
    created_by: str | None = None,
) -> ResearchRun:
    settings = get_settings()
    run = ResearchRun(
        id=uuid.uuid4(),
        status=RunStatus.queued.value,
        brief=_brief_dict(brief),
        model_config_json={
            "openai_model": settings.openai_model,
            "max_tool_calls": settings.max_tool_calls,
            "max_gather_iterations": settings.max_gather_iterations,
            "max_search_results": settings.max_search_results,
            "search_provider": "tavily",
        },
        created_by=created_by,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> ResearchRun | None:
    result = await session.execute(
        select(ResearchRun)
        .where(ResearchRun.id == run_id)
        .options(
            selectinload(ResearchRun.report),
            selectinload(ResearchRun.sources),
        )
    )
    return result.scalar_one_or_none()


async def execute_research_run(run_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        run = await get_run(session, run_id)
        if run is None:
            logger.error("Run %s not found", run_id)
            return

        run.status = RunStatus.running.value
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        await session.commit()

        try:
            graph = get_research_graph()
            final_state = await graph.ainvoke(
                {
                    "run_id": str(run_id),
                    "brief": run.brief,
                    "plan": [],
                    "evidence": [],
                    "report": None,
                    "report_markdown": None,
                    "error": None,
                    "meta": {},
                    "current_node": "start",
                }
            )

            error = final_state.get("error")
            report = final_state.get("report")
            report_markdown = final_state.get("report_markdown")
            evidence = final_state.get("evidence") or []
            plan = final_state.get("plan") or []

            run = await get_run(session, run_id)
            if run is None:
                return

            run.plan = {"steps": plan}
            if error or not report or not report_markdown:
                run.status = RunStatus.failed.value
                run.error_message = error or "Research finished without a report"
                run.finished_at = datetime.now(timezone.utc)
                await session.commit()
                return

            for item in evidence:
                url = item.get("url")
                if not url:
                    continue
                session.add(
                    ResearchSource(
                        run_id=run_id,
                        url=url,
                        title=item.get("title"),
                        snippet=item.get("snippet"),
                        raw_ref={"tool": item.get("tool"), "query": item.get("query")},
                    )
                )

            # Refresh source IDs after flush for stable report source ids
            await session.flush()
            sources_result = await session.execute(
                select(ResearchSource).where(ResearchSource.run_id == run_id)
            )
            db_sources = list(sources_result.scalars().all())
            url_to_id = {source.url: str(source.id) for source in db_sources}

            normalized_sources = []
            for source in report.get("sources") or []:
                url = source.get("url")
                if not url or url not in url_to_id:
                    continue
                normalized_sources.append(
                    {
                        "id": url_to_id[url],
                        "url": url,
                        "title": source.get("title"),
                    }
                )

            sections = []
            for section in report.get("sections") or []:
                citations = []
                for citation in section.get("citations") or []:
                    url = citation.get("url")
                    if url and url in url_to_id:
                        citations.append({"source_id": url_to_id[url], "url": url})
                sections.append(
                    {
                        "heading": section.get("heading"),
                        "content": section.get("content"),
                        "citations": citations,
                    }
                )

            report["sources"] = normalized_sources
            report["sections"] = sections

            session.add(
                ResearchReport(
                    run_id=run_id,
                    report_json=report,
                    report_markdown=report_markdown,
                )
            )
            run.status = RunStatus.completed.value
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = None
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Research run %s failed", run_id)
            run = await get_run(session, run_id)
            if run is None:
                return
            run.status = RunStatus.failed.value
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
