from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from research_agent.agent.llm import get_chat_model
from research_agent.agent.state import ResearchState
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

    llm = get_chat_model().with_structured_output(ResearchPlan)
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
                "snippet": (item.get("snippet") or "")[:800],
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


async def finalize_report(state: ResearchState) -> dict[str, Any]:
    if state.get("error"):
        return {"current_node": "finalize_report"}
    if not state.get("report") or not state.get("report_markdown"):
        return {
            "error": "Report missing at finalize",
            "current_node": "finalize_report",
        }
    return {"current_node": "finalize_report"}
