from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from research_agent.agent.llm import get_chat_model
from research_agent.agent.state import ResearchState
from research_agent.agent.tools.fetch import fetch_url
from research_agent.agent.tools.tavily import tavily_search
from research_agent.core.config import get_settings

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    question: str
    query: str


class ResearchPlan(BaseModel):
    steps: list[PlanStep] = Field(min_length=1, max_length=8)


class ReportSection(BaseModel):
    heading: str
    content: str
    citation_urls: list[str] = Field(default_factory=list)


class StructuredReport(BaseModel):
    title: str
    executive_summary: str
    sections: list[ReportSection] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    risks_or_unknowns: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class SectionVerdict(BaseModel):
    index: int
    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    verdicts: list[SectionVerdict] = Field(default_factory=list)


DEPTH_QUERY_LIMIT = {
    "quick": 2,
    "standard": 4,
    "deep": 6,
}


def _budget_for_depth(depth: str) -> int:
    settings = get_settings()
    return min(DEPTH_QUERY_LIMIT.get(depth, 4), settings.max_gather_iterations)


async def normalize_brief(state: ResearchState) -> dict[str, Any]:
    brief = dict(state.get("brief") or {})
    brief.setdefault("audience", "general")
    brief.setdefault("depth", "standard")
    brief.setdefault("goals", [])
    brief.setdefault("constraints", [])
    brief.setdefault("seed_urls", [])
    return {
        "brief": brief,
        "evidence": list(state.get("evidence") or []),
        "plan": list(state.get("plan") or []),
        "meta": {"tool_calls": 0, "evidence_count": 0},
        "current_node": "normalize_brief",
        "error": None,
    }


async def plan_research(state: ResearchState) -> dict[str, Any]:
    brief = state["brief"]
    depth = brief.get("depth", "standard")
    max_steps = _budget_for_depth(depth)

    llm = get_chat_model(cheap=True).with_structured_output(ResearchPlan)
    prompt = (
        f"Topic: {brief['topic']}\n"
        f"Goals: {brief.get('goals')}\n"
        f"Constraints: {brief.get('constraints')}\n"
        f"Audience: {brief.get('audience')}\n"
        f"Produce at most {max_steps} concrete web search steps."
    )
    plan: ResearchPlan = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You plan business research. Return focused search queries only. "
                    "Do not invent sources."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )
    steps = [
        {"question": step.question, "query": step.query, "status": "pending"}
        for step in plan.steps[:max_steps]
    ]
    return {"plan": steps, "current_node": "plan_research"}


async def gather_evidence(state: ResearchState) -> dict[str, Any]:
    settings = get_settings()
    plan = list(state.get("plan") or [])
    evidence = list(state.get("evidence") or [])
    meta = dict(state.get("meta") or {})
    tool_calls = int(meta.get("tool_calls") or 0)
    seen_urls = {item.get("url") for item in evidence if item.get("url")}

    for step in plan:
        if step.get("status") == "done":
            continue
        if tool_calls >= settings.max_tool_calls:
            break

        query = step.get("query") or step.get("question")
        if not query:
            step["status"] = "done"
            continue

        try:
            results = await tavily_search(query)
            tool_calls += 1
            for item in results:
                url = item["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                evidence.append(
                    {
                        "url": url,
                        "title": item.get("title"),
                        "snippet": item.get("snippet"),
                        "tool": "tavily",
                        "query": query,
                    }
                )
            step["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tavily search failed for query=%s", query)
            step["status"] = "failed"
            step["error"] = str(exc)
            tool_calls += 1

    meta["tool_calls"] = tool_calls
    meta["evidence_count"] = len(evidence)
    return {
        "plan": plan,
        "evidence": evidence,
        "meta": meta,
        "current_node": "gather_evidence",
    }


def _evidence_text(item: dict[str, Any], limit: int) -> str:
    return (item.get("content") or item.get("snippet") or "")[:limit]


async def fetch_pages(state: ResearchState) -> dict[str, Any]:
    """Read the full text of seed URLs and the top search hits (budgeted, SSRF-safe)."""
    settings = get_settings()
    brief = state["brief"]
    evidence = [dict(item) for item in state.get("evidence") or []]
    meta = dict(state.get("meta") or {})

    known = {item.get("url") for item in evidence}
    for url in brief.get("seed_urls") or []:
        if url not in known:
            evidence.insert(0, {"url": url, "title": None, "snippet": None, "tool": "seed"})
            known.add(url)

    targets = [item for item in evidence if not item.get("content")][: settings.max_page_fetches]

    async def _read(item: dict[str, Any]) -> None:
        try:
            page = await fetch_url(item["url"], max_chars=settings.page_fetch_chars)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fetch failed for %s: %s", item["url"], exc)
            item["fetch_error"] = str(exc)[:200]
            return
        item["content"] = page["text"]
        item["fetched_at"] = datetime.now(timezone.utc).isoformat()
        if page.get("title") and not item.get("title"):
            item["title"] = page["title"]

    await asyncio.gather(*(_read(item) for item in targets))

    meta["pages_fetched"] = sum(1 for item in evidence if item.get("content"))
    meta["evidence_count"] = len(evidence)
    return {"evidence": evidence, "meta": meta, "current_node": "fetch_pages"}


def _report_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('title', 'Research Report')}",
        "",
        "## Executive summary",
        report.get("executive_summary", ""),
        "",
    ]
    for section in report.get("sections") or []:
        lines.append(f"## {section.get('heading', 'Section')}")
        if section.get("verified") is False:
            lines.append("> Unverified: not fully supported by the cited sources.")
        lines.append(section.get("content", ""))
        citations = section.get("citations") or []
        if citations:
            lines.append("")
            lines.append("Sources: " + ", ".join(c.get("url", "") for c in citations if c.get("url")))
        lines.append("")

    if report.get("key_findings"):
        lines.append("## Key findings")
        lines.extend(f"- {item}" for item in report["key_findings"])
        lines.append("")

    if report.get("risks_or_unknowns"):
        lines.append("## Risks / unknowns")
        lines.extend(f"- {item}" for item in report["risks_or_unknowns"])
        lines.append("")

    if report.get("follow_up_questions"):
        lines.append("## Follow-up questions")
        lines.extend(f"- {item}" for item in report["follow_up_questions"])
        lines.append("")

    if report.get("sources"):
        lines.append("## Sources")
        for source in report["sources"]:
            title = source.get("title") or source.get("url")
            lines.append(f"- [{title}]({source.get('url')})")

    return "\n".join(lines).strip() + "\n"


async def synthesize_report(state: ResearchState) -> dict[str, Any]:
    brief = state["brief"]
    evidence = state.get("evidence") or []
    if not evidence:
        return {
            "error": "No evidence gathered; cannot synthesize a sourced report",
            "current_node": "synthesize_report",
        }

    evidence_block = json.dumps(
        [
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "text": _evidence_text(item, 2500),
            }
            for item in evidence
        ],
        ensure_ascii=True,
        indent=2,
    )

    llm = get_chat_model().with_structured_output(StructuredReport)
    structured: StructuredReport = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You write business research reports. Use only the provided evidence. "
                    "Every major claim should map to evidence URLs. "
                    "If evidence is weak, say so in risks_or_unknowns. "
                    "citation_urls must be copied from the evidence list — never invent URLs."
                )
            ),
            HumanMessage(
                content=(
                    f"Brief:\n{json.dumps(brief, ensure_ascii=True)}\n\n"
                    f"Evidence:\n{evidence_block}"
                )
            ),
        ]
    )

    allowed_urls = {item["url"] for item in evidence if item.get("url")}
    sources = [
        {
            "id": str(index),
            "url": item["url"],
            "title": item.get("title"),
        }
        for index, item in enumerate(evidence, start=1)
        if item.get("url")
    ]
    url_to_source = {source["url"]: source for source in sources}

    sections = []
    for section in structured.sections:
        citations = []
        for url in section.citation_urls:
            if url in allowed_urls and url in url_to_source:
                citations.append(
                    {
                        "source_id": url_to_source[url]["id"],
                        "url": url,
                    }
                )
        sections.append(
            {
                "heading": section.heading,
                "content": section.content,
                "citations": citations,
            }
        )

    report = {
        "title": structured.title,
        "executive_summary": structured.executive_summary,
        "sections": sections,
        "key_findings": structured.key_findings,
        "risks_or_unknowns": structured.risks_or_unknowns,
        "follow_up_questions": structured.follow_up_questions,
        "sources": [
            {"id": source["id"], "url": source["url"], "title": source.get("title")}
            for source in sources
        ],
    }
    return {
        "report": report,
        "report_markdown": _report_to_markdown(report),
        "current_node": "synthesize_report",
        "error": None,
    }


VERIFY_SYSTEM_PROMPT = (
    "You audit research claims. For each item, decide whether the claims are supported "
    "by the provided source text only. List any specific claims the sources do not "
    "support. Be strict; ignore outside knowledge."
)


async def cite_and_verify(state: ResearchState) -> dict[str, Any]:
    """Check each report section against the text of the sources it cites."""
    settings = get_settings()
    report = state.get("report")
    if state.get("error") or not report:
        return {"current_node": "cite_and_verify"}

    report = json.loads(json.dumps(report))
    meta = dict(state.get("meta") or {})
    evidence_by_url = {item["url"]: item for item in state.get("evidence") or [] if item.get("url")}
    sections = report.get("sections") or []

    payload = []
    for index, section in enumerate(sections):
        cited = [
            {"url": c["url"], "text": _evidence_text(evidence_by_url[c["url"]], 2500)}
            for c in section.get("citations") or []
            if c.get("url") in evidence_by_url
        ]
        if not cited:
            section["verified"] = False
            section["unsupported_claims"] = ["No supporting citation"]
            continue
        payload.append({"index": index, "claims": section.get("content"), "sources": cited})

    meta["verified"] = False
    if payload and settings.verify_claims:
        try:
            llm = get_chat_model(cheap=True).with_structured_output(VerificationResult)
            result: VerificationResult = await llm.ainvoke(
                [
                    SystemMessage(content=VERIFY_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=True)),
                ]
            )
            verdicts = {v.index: v for v in result.verdicts}
            for item in payload:
                verdict = verdicts.get(item["index"])
                if verdict is None:
                    continue
                section = sections[item["index"]]
                section["verified"] = verdict.supported
                if not verdict.supported:
                    section["unsupported_claims"] = verdict.unsupported_claims
            meta["verified"] = True
        except Exception:  # noqa: BLE001
            logger.exception("Claim verification failed; report left unverified")

    unverified = [s for s in sections if s.get("verified") is False]
    for section in unverified:
        claims = "; ".join(section.get("unsupported_claims") or []) or "claims not supported"
        report.setdefault("risks_or_unknowns", []).append(
            f"Unverified: {section.get('heading')} ({claims})"
        )
    meta["unverified_sections"] = len(unverified)
    return {
        "report": report,
        "report_markdown": _report_to_markdown(report),
        "meta": meta,
        "current_node": "cite_and_verify",
    }


async def finalize_report(state: ResearchState) -> dict[str, Any]:
    if state.get("error"):
        return {"current_node": "finalize_report"}
    if not state.get("report") or not state.get("report_markdown"):
        return {
            "error": "Report missing at finalize",
            "current_node": "finalize_report",
        }
    return {"current_node": "finalize_report"}
