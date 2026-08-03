from __future__ import annotations

from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    run_id: str
    brief: dict[str, Any]
    plan: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    report: dict[str, Any] | None
    report_markdown: str | None
    error: str | None
    meta: dict[str, Any]
    current_node: str
