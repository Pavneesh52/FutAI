"""Tool output schemas (IMPLEMENTATION.md section 6.1).

These are shared contracts: tools return them in Phase 3, and they are also the API
response models for `/matches/{id}/events`, `/players` and `/stats` (section 6.4).
Do not change them without updating section 6 and the phase handoff notes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TeamMatchStats(BaseModel):
    """Aggregated team performance in one match."""

    match_id: int
    team_id: int
    team_name: str
    possession_pct: float | None = None
    xg: float | None = None
    shots: int | None = None
    shots_on_target: int | None = None
    passes: int | None = None
    pass_accuracy: float | None = None
    ppda: float | None = None
    field_tilt: float | None = None
    formation: str | None = None


class PlayerMatchStats(BaseModel):
    """Aggregated player performance in one match."""

    match_id: int
    player_id: int
    player_name: str
    team_id: int
    minutes_played: int | None = None
    goals: int | None = None
    assists: int | None = None
    xg: float | None = None
    #: StatsBomb open data has no xA; NULL unless docs/metrics.md documents a proxy.
    xa: float | None = None
    passes: int | None = None
    pass_accuracy: float | None = None
    shots: int | None = None
    tackles: int | None = None
    position_played: str | None = None


class MatchEvent(BaseModel):
    """A single event, with our own surrogate `id` (the source id is a UUID)."""

    id: int
    match_id: int
    minute: int
    second: int
    event_type: str
    team_id: int
    player_id: int | None = None
    x: float | None = None
    y: float | None = None
    outcome: str | None = None
    xg: float | None = None
    related_event_id: int | None = None
    possession_id: int | None = None


class ToolResult(BaseModel):
    """Envelope every tool returns so the LLM sees evidence refs."""

    data: dict[str, Any] | list[Any]
    evidence_refs: list[str] = Field(default_factory=list)
