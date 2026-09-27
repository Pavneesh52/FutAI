"""Tests for the match endpoints, using a stub service so no database is needed."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.api.deps import get_match_data_service
from app.core.errors import MatchNotFoundError
from app.schemas.matches import MatchDetail, MatchSummary, TeamSummary
from app.schemas.tools import MatchEvent, PlayerMatchStats, TeamMatchStats
from app.services.match_data import MatchDataService
from httpx import AsyncClient

from tests.conftest import build_app, build_client, offline_settings

ARGENTINA = TeamSummary(id=779, name="Argentina", country="Argentina")
COLOMBIA = TeamSummary(id=769, name="Colombia", country="Colombia")


def summary(match_id: int = 1) -> MatchSummary:
    return MatchSummary(
        id=match_id,
        home_team=ARGENTINA,
        away_team=COLOMBIA,
        competition="Copa America",
        season="2024",
        match_date=date(2024, 7, 15),
        home_score=1,
        away_score=0,
    )


class StubMatchDataService(MatchDataService):
    """In-memory stand-in for `PostgresMatchDataService`."""

    def __init__(self, known_match_ids: set[int] | None = None) -> None:
        self._known = known_match_ids if known_match_ids is not None else {1}
        self.requested_event_type: str | None = "not-called"

    def _check(self, match_id: int) -> None:
        if match_id not in self._known:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )

    async def list_matches(self) -> list[MatchSummary]:
        return [summary(match_id) for match_id in sorted(self._known)]

    async def get_match(self, match_id: int) -> MatchDetail:
        self._check(match_id)
        return MatchDetail(**summary(match_id).model_dump(), event_count=4146, has_stats=True)

    async def get_events(self, match_id: int, event_type: str | None = None) -> list[MatchEvent]:
        self._check(match_id)
        self.requested_event_type = event_type
        return [
            MatchEvent(
                id=1,
                match_id=match_id,
                minute=111,
                second=0,
                event_type="shot",
                team_id=779,
                player_id=6874,
                x=105.6,
                y=44.0,
                outcome="Goal",
                xg=0.199,
            )
        ]

    async def get_players(self, match_id: int) -> list[PlayerMatchStats]:
        self._check(match_id)
        return [
            PlayerMatchStats(
                match_id=match_id,
                player_id=6874,
                player_name="Lautaro Javier Martinez",
                team_id=779,
                minutes_played=120,
                goals=1,
                shots=4,
                tackles=0,
            )
        ]

    async def get_team_stats(
        self, match_id: int, team_id: int | None = None
    ) -> list[TeamMatchStats]:
        self._check(match_id)
        return [
            TeamMatchStats(match_id=match_id, team_id=779, team_name="Argentina", xg=1.2, shots=12)
        ]


def client_for(service: MatchDataService) -> AsyncClient:
    app = build_app(offline_settings(database_url=""))
    app.dependency_overrides[get_match_data_service] = lambda: service
    return build_client(app)


async def test_list_matches_returns_summaries() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        response = await client.get("/matches")

    assert response.status_code == 200
    body: Any = response.json()
    assert len(body) == 1
    assert body[0]["home_team"]["name"] == "Argentina"
    assert body[0]["competition"] == "Copa America"
    assert body[0]["home_score"] == 1


async def test_get_match_includes_counts() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        response = await client.get("/matches/1")

    assert response.status_code == 200
    body = response.json()
    assert body["event_count"] == 4146
    assert body["has_stats"] is True


async def test_missing_match_returns_404_in_the_standard_envelope() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        response = await client.get("/matches/999999")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "match_not_found"
    assert error["context"] == {"match_id": 999999}
    assert error["request_id"]


async def test_missing_match_also_404s_for_sub_resources() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        events = await client.get("/matches/999999/events")
        players = await client.get("/matches/999999/players")

    assert events.status_code == 404
    assert players.status_code == 404
    assert events.json()["error"]["code"] == "match_not_found"


async def test_events_expose_coordinates_outcome_and_xg() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        response = await client.get("/matches/1/events")

    assert response.status_code == 200
    event = response.json()[0]
    assert event["event_type"] == "shot"
    assert event["minute"] == 111
    assert event["outcome"] == "Goal"
    assert event["xg"] == 0.199
    assert event["x"] == 105.6


async def test_events_accept_an_event_type_filter() -> None:
    service = StubMatchDataService({1})
    async with client_for(service) as client:
        response = await client.get("/matches/1/events", params={"event_type": "shot"})

    assert response.status_code == 200
    assert service.requested_event_type == "shot"


async def test_players_return_minutes_and_goals() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        response = await client.get("/matches/1/players")

    assert response.status_code == 200
    player = response.json()[0]
    assert player["player_name"] == "Lautaro Javier Martinez"
    assert player["minutes_played"] == 120
    assert player["goals"] == 1


async def test_invalid_match_id_type_is_rejected_by_validation() -> None:
    async with client_for(StubMatchDataService({1})) as client:
        response = await client.get("/matches/not-an-int")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
