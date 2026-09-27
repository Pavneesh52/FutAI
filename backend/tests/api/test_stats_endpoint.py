"""Tests for GET /matches/{match_id}/stats endpoint (Phase 2)."""

from __future__ import annotations

from typing import Any

from app.api.deps import get_match_data_service
from app.core.errors import MatchNotFoundError
from app.schemas.matches import MatchDetail, MatchSummary, TeamSummary
from app.schemas.tools import MatchEvent, PlayerMatchStats, TeamMatchStats
from app.services.match_data import MatchDataService
from httpx import AsyncClient

from tests.conftest import build_app, build_client, offline_settings


class StubStatsService(MatchDataService):
    """Stub service with known stats responses."""

    def __init__(self, known_match_ids: set[int] | None = None) -> None:
        self._known = known_match_ids if known_match_ids is not None else {1}
        self.requested_team_id: int | None = None

    def _check(self, match_id: int) -> None:
        if match_id not in self._known:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )

    async def list_matches(self) -> list[MatchSummary]:
        return []

    async def get_match(self, match_id: int) -> MatchDetail:
        self._check(match_id)
        return MatchDetail(
            id=match_id,
            home_team=TeamSummary(id=779, name="Argentina", country="Argentina"),
            away_team=TeamSummary(id=769, name="Colombia", country="Colombia"),
            competition="Copa America",
            season="2024",
            match_date=None,
            home_score=1,
            away_score=0,
            event_count=100,
            has_stats=True,
        )

    async def get_events(self, match_id: int, event_type: str | None = None) -> list[MatchEvent]:
        return []

    async def get_players(self, match_id: int) -> list[PlayerMatchStats]:
        return []

    async def get_team_stats(
        self, match_id: int, team_id: int | None = None
    ) -> list[TeamMatchStats]:
        self._check(match_id)
        self.requested_team_id = team_id

        all_stats = [
            TeamMatchStats(
                match_id=match_id,
                team_id=779,
                team_name="Argentina",
                possession_pct=44.9,
                xg=1.08,
                shots=11,
                shots_on_target=5,
                passes=537,
                pass_accuracy=81.2,
                ppda=39.33,
                field_tilt=0.4358,
                formation="4-3-3",
            ),
            TeamMatchStats(
                match_id=match_id,
                team_id=769,
                team_name="Colombia",
                possession_pct=55.1,
                xg=0.97,
                shots=19,
                shots_on_target=4,
                passes=660,
                pass_accuracy=84.2,
                ppda=13.76,
                field_tilt=0.5642,
                formation="4-2-3-1",
            ),
        ]
        if team_id is not None:
            return [s for s in all_stats if s.team_id == team_id]
        return all_stats


def client_for(service: MatchDataService) -> AsyncClient:
    app = build_app(offline_settings(database_url=""))
    app.dependency_overrides[get_match_data_service] = lambda: service
    return build_client(app)


async def test_get_stats_returns_both_teams() -> None:
    service = StubStatsService({1})
    async with client_for(service) as client:
        response = await client.get("/matches/1/stats")

    assert response.status_code == 200
    body: Any = response.json()
    assert len(body) == 2
    assert body[0]["team_name"] == "Argentina"
    assert body[0]["possession_pct"] == 44.9
    assert body[0]["ppda"] == 39.33
    assert body[0]["field_tilt"] == 0.4358
    assert body[1]["team_name"] == "Colombia"
    assert body[1]["possession_pct"] == 55.1
    assert body[1]["ppda"] == 13.76
    assert body[1]["field_tilt"] == 0.5642


async def test_get_stats_filter_by_team_id() -> None:
    service = StubStatsService({1})
    async with client_for(service) as client:
        response = await client.get("/matches/1/stats", params={"team_id": 769})

    assert response.status_code == 200
    body: Any = response.json()
    assert len(body) == 1
    assert body[0]["team_name"] == "Colombia"
    assert service.requested_team_id == 769


async def test_get_stats_missing_match_404() -> None:
    service = StubStatsService({1})
    async with client_for(service) as client:
        response = await client.get("/matches/999999/stats")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "match_not_found"
    assert error["context"] == {"match_id": 999999}
