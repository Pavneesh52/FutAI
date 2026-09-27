"""Match endpoints (IMPLEMENTATION.md section 6.4).

No business logic here: the router validates input, delegates to `MatchDataService` and
returns the schema. `GET /matches/{id}/stats` arrives in Phase 2, when the metrics it
exposes exist.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_match_data_service
from app.schemas.matches import MatchDetail, MatchSummary
from app.schemas.tools import MatchEvent, PlayerMatchStats, TeamMatchStats
from app.services.match_data import MatchDataService

router = APIRouter(prefix="/matches", tags=["matches"])

ServiceDep = Annotated[MatchDataService, Depends(get_match_data_service)]


@router.get("", response_model=list[MatchSummary], summary="List matches")
async def list_matches(service: ServiceDep) -> list[MatchSummary]:
    """All ingested matches, most recent first."""
    return await service.list_matches()


@router.get("/{match_id}", response_model=MatchDetail, summary="One match")
async def get_match(match_id: int, service: ServiceDep) -> MatchDetail:
    """A match with the counts that tell you what data exists for it."""
    return await service.get_match(match_id)


@router.get(
    "/{match_id}/events",
    response_model=list[MatchEvent],
    summary="A match's events",
)
async def get_events(
    match_id: int,
    service: ServiceDep,
    event_type: Annotated[
        str | None,
        Query(description="Normalised event type, e.g. `shot`, `pass`, `tackle`."),
    ] = None,
) -> list[MatchEvent]:
    """Events in match order, optionally filtered by normalised type."""
    return await service.get_events(match_id, event_type)


@router.get(
    "/{match_id}/players",
    response_model=list[PlayerMatchStats],
    summary="Per-player aggregates for a match",
)
async def get_players(match_id: int, service: ServiceDep) -> list[PlayerMatchStats]:
    """Per-player aggregates, most minutes first. Unused substitutes appear with 0 minutes."""
    return await service.get_players(match_id)


@router.get(
    "/{match_id}/stats",
    response_model=list[TeamMatchStats],
    summary="Per-team match statistics",
)
async def get_team_stats(
    match_id: int,
    service: ServiceDep,
    team_id: Annotated[
        int | None,
        Query(description="Filter by team id; if omitted, returns both teams."),
    ] = None,
) -> list[TeamMatchStats]:
    """Per-team match aggregates (possession %, xG, PPDA, field tilt, shots, passes)."""
    return await service.get_team_stats(match_id, team_id=team_id)
