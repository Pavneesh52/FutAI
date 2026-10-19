"""Deterministic match and team stats tools (Phase 3).

Rule R1 (no invented stats), Rule R2 (typed deterministic tools), Rule R3 (Pydantic validation).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.tools import ToolResult
from app.services.match_data import MatchDataService


class GetMatchStatsInput(BaseModel):
    """Input for get_match_stats."""

    match_id: int = Field(description="The unique ID of the match.")


class GetMatchEventsInput(BaseModel):
    """Input for get_match_events."""

    match_id: int = Field(description="The unique ID of the match.")
    event_type: str | None = Field(
        default=None,
        description="Optional event type to filter on (e.g. 'shot', 'pass', 'tackle', 'goal').",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum number of events to return. Defaults to 25, maximum is 100.",
    )


class GetTeamStatsInput(BaseModel):
    """Input for get_team_stats."""

    team_id: int = Field(description="The unique ID of the team.")
    match_id: int | None = Field(
        default=None,
        description="Optional match ID. Returns stats for that match or across all matches.",
    )


async def get_match_stats(service: MatchDataService, match_id: int) -> ToolResult:
    """Fetch match overview and aggregate stats for both teams in a match.

    Returns possession %, xG, shots, shots on target, passes, pass accuracy, PPDA, and formation.
    """
    stats = await service.get_team_stats(match_id=match_id)
    match_detail = await service.get_match(match_id=match_id)

    evidence_refs: list[str] = [f"team_match_stats:{match_id}:{s.team_id}" for s in stats]

    data: dict[str, Any] = {
        "match": match_detail.model_dump(mode="json"),
        "team_stats": [s.model_dump(mode="json") for s in stats],
    }
    return ToolResult(data=data, evidence_refs=evidence_refs)


async def get_match_events(
    service: MatchDataService,
    match_id: int,
    event_type: str | None = None,
    limit: int = 50,
) -> ToolResult:
    """Fetch events for a match with match minute, second, type, team, coordinates, and xG.

    Returns capped list of events and a truncation indicator.
    """
    events = await service.get_events(match_id=match_id, event_type=event_type)
    total_events = len(events)
    capped_events = events[:limit]
    is_truncated = total_events > limit

    evidence_refs: list[str] = [f"event:{e.id}" for e in capped_events]

    # Compact: drop null fields to save tokens.
    compact: list[dict[str, Any]] = []
    for e in capped_events:
        row: dict[str, Any] = {
            "id": e.id,
            "min": e.minute,
            "sec": e.second,
            "type": e.event_type,
            "team_id": e.team_id,
        }
        if e.player_id is not None:
            row["player_id"] = e.player_id
        if e.outcome:
            row["outcome"] = e.outcome
        if e.xg is not None:
            row["xg"] = round(e.xg, 3)
        compact.append(row)

    data: dict[str, Any] = {
        "match_id": match_id,
        "event_type_filter": event_type,
        "total_count": total_events,
        "returned_count": len(compact),
        "is_truncated": is_truncated,
        "events": compact,
    }
    return ToolResult(data=data, evidence_refs=evidence_refs)


async def get_team_stats(
    service: MatchDataService,
    team_id: int,
    match_id: int | None = None,
) -> ToolResult:
    """Fetch aggregated statistics for a specific team, optionally for a specific match."""
    stats = await service.get_team_stats_for_team(team_id=team_id, match_id=match_id)
    evidence_refs: list[str] = [f"team_match_stats:{s.match_id}:{team_id}" for s in stats]

    data: dict[str, Any] = {
        "team_id": team_id,
        "match_id": match_id,
        "stats": [s.model_dump(mode="json") for s in stats],
    }
    return ToolResult(data=data, evidence_refs=evidence_refs)


class GetMatchPlayersInput(BaseModel):
    """Input for get_match_players."""

    match_id: int = Field(description="The unique ID of the match.")


async def get_match_players(service: MatchDataService, match_id: int) -> ToolResult:
    """Fetch per-player statistics for ALL players in a match.

    Returns goals, assists, xG, passes, pass accuracy, shots, tackles, minutes played,
    and position for every player who appeared, sorted by minutes played descending.
    Use this to compare players or find the best performer in a match.
    """
    players = await service.get_players(match_id=match_id)

    # Only include players who actually played (minutes > 0) to keep payload compact.
    active = [p for p in players if (p.minutes_played or 0) > 0]
    evidence_refs: list[str] = [f"player_match_stats:{match_id}:{p.player_id}" for p in active]

    # Compact representation: drop null/zero fields and match_id (caller knows it).
    compact: list[dict[str, Any]] = []
    for p in active:
        row: dict[str, Any] = {
            "id": p.player_id,
            "name": p.player_name,
            "team_id": p.team_id,
            "mins": p.minutes_played,
        }
        if p.position_played:
            row["pos"] = p.position_played
        if p.goals:
            row["goals"] = p.goals
        if p.assists:
            row["assists"] = p.assists
        if p.xg:
            row["xg"] = round(p.xg, 2)
        if p.shots:
            row["shots"] = p.shots
        if p.passes:
            row["passes"] = p.passes
        if p.pass_accuracy is not None:
            row["pass_pct"] = round(p.pass_accuracy, 1)
        if p.tackles:
            row["tackles"] = p.tackles
        compact.append(row)

    data: dict[str, Any] = {
        "match_id": match_id,
        "player_count": len(compact),
        "players": compact,
    }
    return ToolResult(data=data, evidence_refs=evidence_refs)
