from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class Depth(str, Enum):
    quick = "quick"
    standard = "standard"
    deep = "deep"


class ResearchBriefCreate(BaseModel):
    topic: str = Field(min_length=8, max_length=500)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    audience: str = "general"
    depth: Depth = Depth.standard
    seed_urls: list[HttpUrl] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreateResponse(BaseModel):
    run_id: UUID
    status: str
    created_at: datetime


class RunProgress(BaseModel):
    current_node: str | None = None
    tool_calls: int = 0
    evidence_count: int = 0


class RunStatusResponse(BaseModel):
    run_id: UUID
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    progress: RunProgress | None = None


class SourceOut(BaseModel):
    id: UUID
    url: str
    title: str | None = None


class RunResultResponse(BaseModel):
    run_id: UUID
    status: str
    report: dict[str, Any]
    report_markdown: str
    sources: list[SourceOut]
