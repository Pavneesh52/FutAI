"""Match data access behind a swappable interface (rule R10).

Tools and agents depend on `MatchDataService`, never on SQL. Swapping to a live feed
(Phase 13) means writing another implementation of this class, with no change to
anything above it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import MatchNotFoundError
from app.models import Event, Match, Player, Team
from app.models import PlayerMatchStats as PlayerMatchStatsRow
from app.models import TeamMatchStats as TeamMatchStatsRow
from app.schemas.matches import MatchDetail, MatchSummary, TeamSummary
from app.schemas.tools import MatchEvent
from app.schemas.tools import PlayerMatchStats as PlayerMatchStatsSchema
from app.schemas.tools import TeamMatchStats as TeamMatchStatsSchema


class MatchDataService(ABC):
    """Read-only access to matches, events and aggregates."""

    @abstractmethod
    async def list_matches(self) -> list[MatchSummary]:
        """Every known match, most recent first."""

    @abstractmethod
    async def get_match(self, match_id: int) -> MatchDetail:
        """One match. Raises `MatchNotFoundError` when it does not exist."""

    @abstractmethod
    async def get_events(self, match_id: int, event_type: str | None = None) -> list[MatchEvent]:
        """A match's events in match order, optionally filtered by type."""

    @abstractmethod
    async def get_players(self, match_id: int) -> list[PlayerMatchStatsSchema]:
        """Per-player aggregates for a match, most minutes first."""

    @abstractmethod
    async def get_team_stats(
        self, match_id: int, team_id: int | None = None
    ) -> list[TeamMatchStatsSchema]:
        """Per-team aggregates for a match, optionally for a single team."""

    async def find_player(self, name: str, match_id: int | None = None) -> list[dict[str, Any]]:
        """Find players by name (substring match), optionally scoped to a match."""
        return []

    async def find_team(self, name: str) -> list[dict[str, Any]]:
        """Find teams by name (substring match)."""
        return []

    async def get_player_stats_for_player(
        self, player_id: int, match_id: int | None = None
    ) -> list[PlayerMatchStatsSchema]:
        """Player stats for a specific player across matches or for one match."""
        return []

    async def get_team_stats_for_team(
        self, team_id: int, match_id: int | None = None
    ) -> list[TeamMatchStatsSchema]:
        """Team stats for a specific team across matches or for one match."""
        return []


class PostgresMatchDataService(MatchDataService):
    """The Phase 1 implementation, backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_matches(self) -> list[MatchSummary]:
        home = aliased(Team)
        away = aliased(Team)
        statement = (
            select(Match, home, away)
            .join(home, Match.home_team_id == home.id)
            .join(away, Match.away_team_id == away.id)
            .order_by(Match.match_date.desc(), Match.id.desc())
        )
        rows = (await self._session.execute(statement)).all()
        return [self._summary(match, home_team, away_team) for match, home_team, away_team in rows]

    async def get_match(self, match_id: int) -> MatchDetail:
        match, home_team, away_team = await self._fetch_match(match_id)
        internal_id = match.id
        summary = self._summary(match, home_team, away_team)

        event_count = (
            await self._session.execute(
                select(func.count()).select_from(Event).where(Event.match_id == internal_id)
            )
        ).scalar_one()
        stats_count = (
            await self._session.execute(
                select(func.count())
                .select_from(TeamMatchStatsRow)
                .where(TeamMatchStatsRow.match_id == internal_id)
            )
        ).scalar_one()

        return MatchDetail(
            **summary.model_dump(), event_count=int(event_count), has_stats=int(stats_count) > 0
        )

    async def get_events(self, match_id: int, event_type: str | None = None) -> list[MatchEvent]:
        internal_id = await self._resolve_match_id(match_id)

        statement = (
            select(Event)
            .where(Event.match_id == internal_id)
            .order_by(Event.minute, Event.second, Event.id)
        )
        if event_type is not None:
            statement = statement.where(Event.event_type == event_type)

        rows = (await self._session.execute(statement)).scalars().all()
        return [MatchEvent.model_validate(row, from_attributes=True) for row in rows]

    async def get_players(self, match_id: int) -> list[PlayerMatchStatsSchema]:
        internal_id = await self._resolve_match_id(match_id)

        statement = (
            select(PlayerMatchStatsRow, Player.name)
            .join(Player, PlayerMatchStatsRow.player_id == Player.id)
            .where(PlayerMatchStatsRow.match_id == internal_id)
            .order_by(
                PlayerMatchStatsRow.minutes_played.desc().nullslast(),
                Player.name,
            )
        )
        rows = (await self._session.execute(statement)).all()

        return [
            PlayerMatchStatsSchema(
                match_id=stats.match_id,
                player_id=stats.player_id,
                player_name=name,
                team_id=stats.team_id,
                minutes_played=stats.minutes_played,
                goals=stats.goals,
                assists=stats.assists,
                xg=stats.xg,
                xa=stats.xa,
                passes=stats.passes,
                pass_accuracy=stats.pass_accuracy,
                shots=stats.shots,
                tackles=stats.tackles,
                position_played=stats.position_played,
            )
            for stats, name in rows
        ]

    async def get_team_stats(
        self, match_id: int, team_id: int | None = None
    ) -> list[TeamMatchStatsSchema]:
        internal_id = await self._resolve_match_id(match_id)

        statement = (
            select(TeamMatchStatsRow, Team.name)
            .join(Team, TeamMatchStatsRow.team_id == Team.id)
            .where(TeamMatchStatsRow.match_id == internal_id)
            .order_by(Team.name)
        )
        if team_id is not None:
            statement = statement.where(TeamMatchStatsRow.team_id == team_id)

        rows = (await self._session.execute(statement)).all()

        return [
            TeamMatchStatsSchema(
                match_id=stats.match_id,
                team_id=stats.team_id,
                team_name=name,
                possession_pct=stats.possession_pct,
                xg=stats.xg,
                shots=stats.shots,
                shots_on_target=stats.shots_on_target,
                passes=stats.passes,
                pass_accuracy=stats.pass_accuracy,
                ppda=stats.ppda,
                field_tilt=stats.field_tilt,
                formation=stats.formation,
            )
            for stats, name in rows
        ]

    async def find_player(self, name: str, match_id: int | None = None) -> list[dict[str, Any]]:
        search = f"%{name}%"
        if match_id is not None:
            internal_id = await self._resolve_match_id(match_id)
            statement = (
                select(Player.id, Player.name, Team.id, Team.name)
                .join(PlayerMatchStatsRow, PlayerMatchStatsRow.player_id == Player.id)
                .join(Team, PlayerMatchStatsRow.team_id == Team.id)
                .where(PlayerMatchStatsRow.match_id == internal_id, Player.name.ilike(search))
                .distinct()
                .order_by(Player.name)
            )
        else:
            statement = (
                select(Player.id, Player.name, Team.id, Team.name)
                .outerjoin(Team, Player.team_id == Team.id)
                .where(Player.name.ilike(search))
                .distinct()
                .order_by(Player.name)
            )
        rows = (await self._session.execute(statement)).all()
        return [
            {
                "player_id": r[0],
                "player_name": r[1],
                "team_id": r[2],
                "team_name": r[3] or "",
            }
            for r in rows
        ]

    async def find_team(self, name: str) -> list[dict[str, Any]]:
        search = f"%{name}%"
        statement = (
            select(Team.id, Team.name, Team.country)
            .where(Team.name.ilike(search))
            .order_by(Team.name)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            {
                "team_id": r[0],
                "team_name": r[1],
                "country": r[2],
            }
            for r in rows
        ]

    async def get_player_stats_for_player(
        self, player_id: int, match_id: int | None = None
    ) -> list[PlayerMatchStatsSchema]:
        statement = (
            select(PlayerMatchStatsRow, Player.name)
            .join(Player, PlayerMatchStatsRow.player_id == Player.id)
            .where(PlayerMatchStatsRow.player_id == player_id)
            .order_by(PlayerMatchStatsRow.match_id.desc())
        )
        if match_id is not None:
            internal_id = await self._resolve_match_id(match_id)
            statement = statement.where(PlayerMatchStatsRow.match_id == internal_id)

        rows = (await self._session.execute(statement)).all()
        return [
            PlayerMatchStatsSchema(
                match_id=stats.match_id,
                player_id=stats.player_id,
                player_name=name,
                team_id=stats.team_id,
                minutes_played=stats.minutes_played,
                goals=stats.goals,
                assists=stats.assists,
                xg=stats.xg,
                xa=stats.xa,
                passes=stats.passes,
                pass_accuracy=stats.pass_accuracy,
                shots=stats.shots,
                tackles=stats.tackles,
                position_played=stats.position_played,
            )
            for stats, name in rows
        ]

    async def get_team_stats_for_team(
        self, team_id: int, match_id: int | None = None
    ) -> list[TeamMatchStatsSchema]:
        statement = (
            select(TeamMatchStatsRow, Team.name)
            .join(Team, TeamMatchStatsRow.team_id == Team.id)
            .where(TeamMatchStatsRow.team_id == team_id)
            .order_by(TeamMatchStatsRow.match_id.desc())
        )
        if match_id is not None:
            internal_id = await self._resolve_match_id(match_id)
            statement = statement.where(TeamMatchStatsRow.match_id == internal_id)

        rows = (await self._session.execute(statement)).all()
        return [
            TeamMatchStatsSchema(
                match_id=stats.match_id,
                team_id=stats.team_id,
                team_name=name,
                possession_pct=stats.possession_pct,
                xg=stats.xg,
                shots=stats.shots,
                shots_on_target=stats.shots_on_target,
                passes=stats.passes,
                pass_accuracy=stats.pass_accuracy,
                ppda=stats.ppda,
                field_tilt=stats.field_tilt,
                formation=stats.formation,
            )
            for stats, name in rows
        ]

    async def _resolve_match_id(self, match_id: int) -> int:
        statement = select(Match.id).where(
            (Match.id == match_id) | (Match.source_id == str(match_id))
        )
        row = (await self._session.execute(statement)).first()
        if row is None:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )
        return int(row[0])

    async def _fetch_match(self, match_id: int) -> tuple[Match, Team, Team]:
        home = aliased(Team)
        away = aliased(Team)
        statement = (
            select(Match, home, away)
            .join(home, Match.home_team_id == home.id)
            .join(away, Match.away_team_id == away.id)
            .where((Match.id == match_id) | (Match.source_id == str(match_id)))
        )
        row = (await self._session.execute(statement)).first()
        if row is None:
            raise MatchNotFoundError(
                f"No match with id {match_id}.", context={"match_id": match_id}
            )
        return row[0], row[1], row[2]

    async def _ensure_match(self, match_id: int) -> None:
        await self._resolve_match_id(match_id)

    @staticmethod
    def _summary(match: Match, home_team: Team, away_team: Team) -> MatchSummary:
        return MatchSummary(
            id=match.id,
            home_team=TeamSummary(id=home_team.id, name=home_team.name, country=home_team.country),
            away_team=TeamSummary(id=away_team.id, name=away_team.name, country=away_team.country),
            competition=match.competition,
            season=match.season,
            match_date=match.match_date,
            home_score=match.home_score,
            away_score=match.away_score,
        )
