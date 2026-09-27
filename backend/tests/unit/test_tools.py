"""Unit tests for deterministic tools and tool registry (Rule R8: unit-testable with no LLM)."""

from __future__ import annotations

from typing import Any

import pytest
from app.core.errors import MatchNotFoundError, ToolExecutionError, ValidationFailedError
from app.schemas.matches import MatchDetail, MatchSummary, TeamSummary
from app.schemas.tools import MatchEvent
from app.schemas.tools import PlayerMatchStats as PlayerMatchStatsSchema
from app.schemas.tools import TeamMatchStats as TeamMatchStatsSchema
from app.services.match_data import MatchDataService
from app.tools.match_tools import get_match_events, get_match_stats
from app.tools.player_tools import (
    PlayerMetricEnum,
    calculate_player_metric,
    find_player,
    find_team,
)
from app.tools.registry import create_default_tool_registry


class StubMatchDataService(MatchDataService):
    """In-memory stub implementing MatchDataService for deterministic tool unit tests."""

    def __init__(self) -> None:
        self.matches: dict[int, MatchDetail] = {
            100: MatchDetail(
                id=100,
                home_team=TeamSummary(id=1, name="Arsenal", country="England"),
                away_team=TeamSummary(id=2, name="Chelsea", country="England"),
                competition="Premier League",
                season="2023/2024",
                match_date="2024-04-23",  # type: ignore[arg-type]
                home_score=5,
                away_score=0,
                event_count=3,
                has_stats=True,
            )
        }
        self.team_stats: dict[int, list[TeamMatchStatsSchema]] = {
            100: [
                TeamMatchStatsSchema(
                    match_id=100,
                    team_id=1,
                    team_name="Arsenal",
                    possession_pct=55.4,
                    xg=2.85,
                    shots=16,
                    shots_on_target=10,
                    passes=450,
                    pass_accuracy=87.5,
                    ppda=8.2,
                    field_tilt=0.62,
                    formation="4-3-3",
                ),
                TeamMatchStatsSchema(
                    match_id=100,
                    team_id=2,
                    team_name="Chelsea",
                    possession_pct=44.6,
                    xg=0.75,
                    shots=7,
                    shots_on_target=1,
                    passes=360,
                    pass_accuracy=81.0,
                    ppda=14.5,
                    field_tilt=0.38,
                    formation="4-2-3-1",
                ),
            ]
        }
        self.events: dict[int, list[MatchEvent]] = {
            100: [
                MatchEvent(
                    id=1,
                    match_id=100,
                    minute=4,
                    second=15,
                    event_type="pass",
                    team_id=1,
                    x=45.0,
                    y=30.0,
                    outcome="complete",
                ),
                MatchEvent(
                    id=2,
                    match_id=100,
                    minute=4,
                    second=18,
                    event_type="shot",
                    team_id=1,
                    player_id=10,
                    x=105.0,
                    y=38.0,
                    outcome="goal",
                    xg=0.35,
                ),
                MatchEvent(
                    id=3,
                    match_id=100,
                    minute=12,
                    second=0,
                    event_type="foul_committed",
                    team_id=2,
                    player_id=20,
                    x=50.0,
                    y=40.0,
                ),
            ]
        }
        self.player_stats: dict[int, list[PlayerMatchStatsSchema]] = {
            100: [
                PlayerMatchStatsSchema(
                    match_id=100,
                    player_id=10,
                    player_name="Bukayo Saka",
                    team_id=1,
                    minutes_played=90,
                    goals=1,
                    assists=1,
                    xg=0.45,
                    passes=35,
                    pass_accuracy=88.0,
                    shots=3,
                    tackles=2,
                    position_played="Right Wing",
                ),
                PlayerMatchStatsSchema(
                    match_id=100,
                    player_id=11,
                    player_name="Martin Odegaard",
                    team_id=1,
                    minutes_played=85,
                    goals=0,
                    assists=2,
                    xg=0.20,
                    passes=55,
                    pass_accuracy=92.0,
                    shots=2,
                    tackles=1,
                    position_played="Center Midfield",
                ),
            ]
        }

    async def list_matches(self) -> list[MatchSummary]:
        return list(self.matches.values())

    async def get_match(self, match_id: int) -> MatchDetail:
        if match_id not in self.matches:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )
        return self.matches[match_id]

    async def get_events(self, match_id: int, event_type: str | None = None) -> list[MatchEvent]:
        if match_id not in self.matches:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )
        events = self.events.get(match_id, [])
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    async def get_players(self, match_id: int) -> list[PlayerMatchStatsSchema]:
        if match_id not in self.matches:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )
        return self.player_stats.get(match_id, [])

    async def get_team_stats(
        self, match_id: int, team_id: int | None = None
    ) -> list[TeamMatchStatsSchema]:
        if match_id not in self.matches:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )
        stats = self.team_stats.get(match_id, [])
        if team_id is not None:
            stats = [s for s in stats if s.team_id == team_id]
        return stats

    async def find_player(self, name: str, match_id: int | None = None) -> list[dict[str, Any]]:
        results = []
        name_lower = name.lower()
        for m_id, players in self.player_stats.items():
            if match_id is not None and m_id != match_id:
                continue
            for p in players:
                if name_lower in p.player_name.lower():
                    results.append(
                        {
                            "player_id": p.player_id,
                            "player_name": p.player_name,
                            "team_id": p.team_id,
                            "team_name": "Arsenal" if p.team_id == 1 else "Chelsea",
                        }
                    )
        return results

    async def find_team(self, name: str) -> list[dict[str, Any]]:
        teams = [
            {"team_id": 1, "team_name": "Arsenal", "country": "England"},
            {"team_id": 2, "team_name": "Chelsea", "country": "England"},
        ]
        return [t for t in teams if name.lower() in t["team_name"].lower()]

    async def get_player_stats_for_player(
        self, player_id: int, match_id: int | None = None
    ) -> list[PlayerMatchStatsSchema]:
        results = []
        for m_id, players in self.player_stats.items():
            if match_id is not None and m_id != match_id:
                continue
            for p in players:
                if p.player_id == player_id:
                    results.append(p)
        return results

    async def get_team_stats_for_team(
        self, team_id: int, match_id: int | None = None
    ) -> list[TeamMatchStatsSchema]:
        results = []
        for m_id, stats in self.team_stats.items():
            if match_id is not None and m_id != match_id:
                continue
            for s in stats:
                if s.team_id == team_id:
                    results.append(s)
        return results


@pytest.fixture
def stub_service() -> StubMatchDataService:
    return StubMatchDataService()


@pytest.mark.asyncio
async def test_get_match_stats(stub_service: StubMatchDataService) -> None:
    res = await get_match_stats(stub_service, match_id=100)
    assert "team_match_stats:100:1" in res.evidence_refs
    assert "team_match_stats:100:2" in res.evidence_refs
    assert res.data["match"]["home_score"] == 5
    assert len(res.data["team_stats"]) == 2


@pytest.mark.asyncio
async def test_get_match_events_filtering_and_truncation(
    stub_service: StubMatchDataService,
) -> None:
    res = await get_match_events(stub_service, match_id=100, event_type="shot")
    assert len(res.data["events"]) == 1
    assert res.data["events"][0]["type"] == "shot"
    assert "event:2" in res.evidence_refs
    assert res.data["is_truncated"] is False

    # Test limit truncation
    res_trunc = await get_match_events(stub_service, match_id=100, limit=2)
    assert res_trunc.data["returned_count"] == 2
    assert res_trunc.data["total_count"] == 3
    assert res_trunc.data["is_truncated"] is True


@pytest.mark.asyncio
async def test_find_player_and_team_resolvers(stub_service: StubMatchDataService) -> None:
    player_res = await find_player(stub_service, name="Saka")
    assert len(player_res.data["candidates"]) == 1
    assert player_res.data["candidates"][0]["player_name"] == "Bukayo Saka"
    assert player_res.evidence_refs == []

    team_res = await find_team(stub_service, name="arsenal")
    assert len(team_res.data["candidates"]) == 1
    assert team_res.data["candidates"][0]["team_name"] == "Arsenal"


@pytest.mark.asyncio
async def test_calculate_player_metric(stub_service: StubMatchDataService) -> None:
    goals_res = await calculate_player_metric(
        stub_service, player_id=10, metric=PlayerMetricEnum.GOALS
    )
    assert goals_res.data["value"] == 1
    assert "player_match_stats:100:10" in goals_res.evidence_refs

    assists_res = await calculate_player_metric(stub_service, player_id=11, metric="assists")
    assert assists_res.data["value"] == 2

    # Non-existent player
    empty_res = await calculate_player_metric(stub_service, player_id=999, metric="goals")
    assert empty_res.data["value"] is None
    assert empty_res.evidence_refs == []


@pytest.mark.asyncio
async def test_tool_registry_execution(stub_service: StubMatchDataService) -> None:
    registry = create_default_tool_registry()
    schemas = registry.get_openai_tool_schemas()
    assert len(schemas) == 8

    # Test execution
    res = await registry.execute("get_match_stats", {"match_id": 100}, stub_service)
    assert "team_match_stats:100:1" in res.evidence_refs

    # Test invalid input raises ValidationFailedError
    with pytest.raises(ValidationFailedError):
        await registry.execute("get_match_stats", {"match_id": "not_an_int"}, stub_service)

    # Test unregistered tool raises ToolExecutionError
    with pytest.raises(ToolExecutionError):
        await registry.execute("non_existent_tool", {}, stub_service)
