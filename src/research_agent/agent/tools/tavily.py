from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from research_agent.core.config import get_settings

logger = logging.getLogger(__name__)


async def tavily_search(query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    limit = max_results or settings.max_search_results
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query[:500],
        "max_results": limit,
        "include_answer": False,
        "search_depth": "basic",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post("https://api.tavily.com/search", json=payload)
        response.raise_for_status()
        data = response.json()

    results: list[dict[str, Any]] = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        results.append(
            {
                "url": url,
                "title": item.get("title"),
                "snippet": item.get("content") or item.get("snippet"),
                "tool": "tavily",
                "raw": item,
            }
        )
    return results
