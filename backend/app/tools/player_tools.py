"""Deterministic player statistics, metric calculation, and resolver tools (Phase 3).

Rule R1 (no invented stats), Rule R2 (typed deterministic tools), Rule R3 (Pydantic validation).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.schemas.tools import ToolResult
from app.services.match_data import MatchDataService


class PlayerMetricEnum(StrEnum):
    """Supported player metrics for calculation."""

    GOALS = "goals"
    ASSISTS = "assists"
    XG = "xg"
    XA = "xa"
    PASSES = "passes"
    PASS_ACCURACY = "pass_accuracy"
    SHOTS = "shots"
    TACKLES = "tackles"
    MINUTES_PLAYED = "minutes_played"


class FindPlayerInput(BaseModel):
    """Input for find_player resolver."""

    name: str = Field(description="The name or partial name of the player to look up.")
    match_id: int | None = Field(
        default=None,
        description="Optional match ID. Limits the search to players who appeared in that match.",
    )


class FindTeamInput(BaseModel):
    """Input for find_team resolver."""

    name: str = Field(description="The name or partial name of the team to look up.")


class GetPlayerStatsInput(BaseModel):
    """Input for get_player_stats."""

    player_id: int = Field(description="The unique ID of the player.")
    match_id: int | None = Field(
        default=None,
        description="Optional match ID. Returns stats for that match or across all matches.",
    )


class CalculatePlayerMetricInput(BaseModel):
    """Input for calculate_player_metric."""

    player_id: int = Field(description="The unique ID of the player.")
    metric: PlayerMetricEnum = Field(description="The metric to compute/retrieve.")
    match_id: int | None = Field(
        default=None,
        description="Optional match ID. Evaluates the metric for that match or across matches.",
    )


async def find_player(
    service: MatchDataService,
    name: str,
    match_id: int | None = None,
) -> ToolResult:
    """Resolve a player's natural name to candidate IDs and teams.

    Always use this before querying player stats if only a player name is known.
    """
    candidates = await service.find_player(name=name, match_id=match_id)
    return ToolResult(
        data={"query": name, "match_id": match_id, "candidates": candidates},
        evidence_refs=[],
    )


async def find_team(
    service: MatchDataService,
    name: str,
) -> ToolResult:
    """Resolve a team's natural name to candidate IDs and countries.

    Always use this before querying team stats if only a team name is known.
    """
    candidates = await service.find_team(name=name)
    return ToolResult(
        data={"query": name, "candidates": candidates},
        evidence_refs=[],
    )


async def get_player_stats(
    service: MatchDataService,
    player_id: int,
    match_id: int | None = None,
) -> ToolResult:
    """Fetch recorded match statistics for a specific player."""
    stats = await service.get_player_stats_for_player(player_id=player_id, match_id=match_id)
    evidence_refs: list[str] = [f"player_match_stats:{s.match_id}:{player_id}" for s in stats]

    data: dict[str, Any] = {
        "player_id": player_id,
        "match_id": match_id,
        "stats": [s.model_dump(mode="json") for s in stats],
    }
    return ToolResult(data=data, evidence_refs=evidence_refs)


async def calculate_player_metric(
    service: MatchDataService,
    player_id: int,
    metric: PlayerMetricEnum | str,
    match_id: int | None = None,
) -> ToolResult:
    """Calculate or aggregate a specific metric for a player (e.g. goals, assists, xG, tackles)."""
    metric_str = metric.value if isinstance(metric, PlayerMetricEnum) else str(metric)
    stats = await service.get_player_stats_for_player(player_id=player_id, match_id=match_id)

    if not stats:
        return ToolResult(
            data={
                "player_id": player_id,
                "metric": metric_str,
                "value": None,
                "matches_counted": 0,
                "message": "No statistics recorded for this player in the requested scope.",
            },
            evidence_refs=[],
        )

    evidence_refs = [f"player_match_stats:{s.match_id}:{player_id}" for s in stats]

    # Calculate metric
    if metric_str == PlayerMetricEnum.GOALS.value:
        val: float | int | None = sum((s.goals or 0) for s in stats)
    elif metric_str == PlayerMetricEnum.ASSISTS.value:
        val = sum((s.assists or 0) for s in stats)
    elif metric_str == PlayerMetricEnum.XG.value:
        val = round(sum((s.xg or 0.0) for s in stats), 3)
    elif metric_str == PlayerMetricEnum.XA.value:
        val = (
            round(sum((s.xa or 0.0) for s in stats), 3)
            if any(s.xa is not None for s in stats)
            else None
        )
    elif metric_str == PlayerMetricEnum.PASSES.value:
        val = sum((s.passes or 0) for s in stats)
    elif metric_str == PlayerMetricEnum.SHOTS.value:
        val = sum((s.shots or 0) for s in stats)
    elif metric_str == PlayerMetricEnum.TACKLES.value:
        val = sum((s.tackles or 0) for s in stats)
    elif metric_str == PlayerMetricEnum.MINUTES_PLAYED.value:
        val = sum((s.minutes_played or 0) for s in stats)
    elif metric_str == PlayerMetricEnum.PASS_ACCURACY.value:
        total_passes = sum((s.passes or 0) for s in stats)
        if total_passes > 0:
            # Weighted average
            completed = sum(((s.pass_accuracy or 0.0) / 100.0 * (s.passes or 0)) for s in stats)
            val = round(100.0 * completed / total_passes, 1)
        else:
            val = None
    else:
        raise AppError(f"Unsupported player metric: {metric_str}", context={"metric": metric_str})

    data: dict[str, Any] = {
        "player_id": player_id,
        "player_name": stats[0].player_name if stats else None,
        "metric": metric_str,
        "value": val,
        "matches_counted": len(stats),
    }
    return ToolResult(data=data, evidence_refs=evidence_refs)
