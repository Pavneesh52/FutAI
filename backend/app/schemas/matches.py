"""Match response models (IMPLEMENTATION.md section 6.4)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TeamSummary(BaseModel):
    """A team, as embedded in a match summary."""

    id: int
    name: str
    country: str | None = None


class MatchSummary(BaseModel):
    """One row of `GET /matches`."""

    id: int
    home_team: TeamSummary
    away_team: TeamSummary
    competition: str
    season: str
    match_date: date
    home_score: int | None = Field(default=None, description="NULL if not played in the source.")
    away_score: int | None = None


class MatchDetail(MatchSummary):
    """`GET /matches/{id}`: a summary plus what the match actually contains."""

    event_count: int = Field(description="Number of ingested events.")
    has_stats: bool = Field(description="True once team_match_stats rows exist for this match.")
