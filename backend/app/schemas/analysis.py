"""Analysis API request and response schemas (IMPLEMENTATION.md section 6.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """Payload for POST /analysis."""

    query: str
    match_id: int | None = None


class EvidenceItem(BaseModel):
    """One resolved evidence_ref, rendered in the UI's Evidence list."""

    ref: str
    label: str
    value: str | float | int | list | dict | None = None


class SourceItem(BaseModel):
    """RAG citations only (Phase 7)."""

    title: str
    url: str


class AnalysisResult(BaseModel):
    """Response contract for POST /analysis and base for specialized queries."""

    run_id: str
    query_type: Literal["simple_stat", "player", "tactical", "comparison", "report"]
    answer_markdown: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    degraded: bool = False
    retry_count: int = 0


class TacticalAnalysisResult(AnalysisResult):
    """Response contract for POST /analysis/tactical."""

    match_id: int
    report_id: int | None = None


class PlayerAnalysisResult(AnalysisResult):
    """Response contract for POST /analysis/player."""

    match_id: int
    player_id: int
    report_id: int | None = None


class ComparisonResult(AnalysisResult):
    """Response contract for POST /analysis/comparison."""

    match_id_a: int
    match_id_b: int
    report_id: int | None = None


class Report(BaseModel):
    """Persistent report entity (Phase 6)."""

    id: int
    agent_run_id: str
    match_id: int | None = None
    content: str
    created_at: datetime
