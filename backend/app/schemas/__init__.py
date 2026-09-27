"""Pydantic request/response models.

Section 6.1 (tool outputs), section 6.2 (agent contracts),
section 6.4 (match and analysis models) and health.
"""

from __future__ import annotations

from app.schemas.agents import AgentFinding, CriticIssue, CriticResult
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    ComparisonResult,
    EvidenceItem,
    PlayerAnalysisResult,
    Report,
    SourceItem,
    TacticalAnalysisResult,
)
from app.schemas.health import HealthResponse
from app.schemas.matches import MatchDetail, MatchSummary, TeamSummary
from app.schemas.tools import MatchEvent, PlayerMatchStats, TeamMatchStats, ToolResult

__all__ = [
    "AgentFinding",
    "AnalysisRequest",
    "AnalysisResult",
    "ComparisonResult",
    "CriticIssue",
    "CriticResult",
    "EvidenceItem",
    "HealthResponse",
    "MatchDetail",
    "MatchEvent",
    "MatchSummary",
    "PlayerAnalysisResult",
    "PlayerMatchStats",
    "Report",
    "SourceItem",
    "TacticalAnalysisResult",
    "TeamMatchStats",
    "TeamSummary",
    "ToolResult",
]
