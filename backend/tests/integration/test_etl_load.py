"""The ETL against a real Postgres.

The unit tests prove the parsing; these prove the *loading*: that rows land with the right
relationships, that re-running duplicates nothing (the property Phase 1 is graded on), and
that the numbers in the database are the ones verified by hand from the raw feed.
"""

from __future__ import annotations

import pytest
from app.etl.statsbomb import MAX_PERIOD
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import (
    FINAL,
    QUARTER_FINAL,
    load_fixture,
    load_fixture_match,
    requires_postgres,
    table_counts,
    truncate_all,
)

pytestmark = pytest.mark.integration

ARGENTINA = 779
COLOMBIA = 769
ECUADOR = 3565


async def _load_both_fixtures(session: AsyncSession) -> dict[str, int]:
    """Load both committed matches and commit, as `scripts/seed.py` would."""
    totals = {"events": 0, "events_skipped_shootout": 0, "player_stats": 0, "formations": 0}
    for match_id in (FINAL, QUARTER_FINAL):
        counts = await load_fixture_match(session, match_id)
        for key in totals:
            totals[key] += counts[key]
    await session.commit()
    return totals


@requires_postgres
async def test_load_is_idempotent(session: AsyncSession) -> None:
    """Running the ETL twice must leave the database exactly as the first run did."""
    await truncate_all(session)

    first = await _load_both_fixtures(session)
    after_first = await table_counts(session)

    second = await _load_both_fixtures(session)
    after_second = await table_counts(session)

    assert first == second
    assert after_first == after_second
    # Non-trivial load, so an empty-database pass-through cannot fake success.
    assert after_first["events"] > 6000
    assert after_first["team_match_stats"] == 4  # two matches x two teams


@requires_postgres
async def test_loaded_row_counts_match_the_fixtures(session: AsyncSession) -> None:
    await truncate_all(session)
    await _load_both_fixtures(session)

    # Only periods 1-4 are loaded: the quarter-final's 22 shootout events are dropped.
    expected_events = sum(
        sum(1 for event in load_fixture("events", match_id) if int(event["period"]) <= MAX_PERIOD)
        for match_id in (FINAL, QUARTER_FINAL)
    )
    assert await session.scalar(text("select count(*) from events")) == expected_events

    # Squads repeat across matches (Argentina played both), so players are distinct ids.
    expected_players = {
        player["player_id"]
        for match_id in (FINAL, QUARTER_FINAL)
        for team in load_fixture("lineups", match_id)
        for player in team["lineup"]
    }
    assert await session.scalar(text("select count(*) from players")) == len(expected_players)
    assert await session.scalar(text("select count(*) from teams")) == 3
    assert await session.scalar(text("select count(*) from matches")) == 2

    # Both matches are complete: every team appears in the stats table.
    assert await session.scalar(text("select count(distinct team_id) from team_match_stats")) == 3
    # Argentina's two lineups are stored once, not once per match.
    assert (
        await session.scalar(
            text("select count(*) from players where source_id = :sid"),
            {"sid": f"statsbomb:player:{11456}"},
        )
        == 1
    )


@requires_postgres
async def test_foreign_keys_reference_the_right_team(session: AsyncSession) -> None:
    """The relationships have to be right, not merely present."""
    await truncate_all(session)
    await _load_both_fixtures(session)

    # Every event belongs to a player who plays for the event's own team.
    cross_team_events = await session.scalar(
        text(
            """
            select count(*)
            from events e
            join players p on p.id = e.player_id
            where p.team_id <> e.team_id
            """
        )
    )
    assert cross_team_events == 0

    # Every event and stat row belongs to one of the match's two teams.
    stray_events = await session.scalar(
        text(
            """
            select count(*)
            from events e
            join matches m on m.id = e.match_id
            where e.team_id not in (m.home_team_id, m.away_team_id)
            """
        )
    )
    assert stray_events == 0

    stray_stats = await session.scalar(
        text(
            """
            select count(*)
            from player_match_stats s
            join matches m on m.id = s.match_id
            where s.team_id not in (m.home_team_id, m.away_team_id)
            """
        )
    )
    assert stray_stats == 0

    # No event lost its team or its match on the way in.
    assert (
        await session.scalar(
            text("select count(*) from events where team_id is null or match_id is null")
        )
        == 0
    )


@requires_postgres
async def test_stored_numbers_match_the_hand_verified_aggregates(session: AsyncSession) -> None:
    await truncate_all(session)
    await _load_both_fixtures(session)

    argentina = (
        await session.execute(
            text(
                """
                select s.shots, s.shots_on_target, s.xg, s.passes
                from team_match_stats s
                join matches m on m.id = s.match_id
                join teams t on t.id = s.team_id
                where m.source_id = :match and t.name = 'Argentina'
                """
            ),
            {"match": f"statsbomb:match:{FINAL}"},
        )
    ).one()
    assert (argentina.shots, argentina.shots_on_target) == (11, 5)
    assert float(argentina.xg) == pytest.approx(1.0827, abs=1e-3)

    colombia = (
        await session.execute(
            text(
                """
                select s.shots, s.shots_on_target, s.xg
                from team_match_stats s
                join matches m on m.id = s.match_id
                join teams t on t.id = s.team_id
                where m.source_id = :match and t.name = 'Colombia'
                """
            ),
            {"match": f"statsbomb:match:{FINAL}"},
        )
    ).one()
    assert (colombia.shots, colombia.shots_on_target) == (19, 4)
    assert float(colombia.xg) == pytest.approx(0.9723, abs=1e-3)

    # Goals: one in the final, two in the quarter-final. The shootout's six are excluded.
    goals = (
        await session.execute(
            text(
                """
                select p.name, e.minute, m.source_id
                from events e
                join players p on p.id = e.player_id
                join matches m on m.id = e.match_id
                where e.event_type = 'shot' and e.outcome = 'Goal'
                order by e.minute
                """
            )
        )
    ).all()
    assert len(goals) == 3
    winner = [goal for goal in goals if goal.source_id == f"statsbomb:match:{FINAL}"]
    assert len(winner) == 1
    assert winner[0].name.startswith("Lautaro")
    assert winner[0].minute == 111


@requires_postgres
async def test_minutes_played_are_plausible_for_both_sides(session: AsyncSession) -> None:
    """The lineups' overlapping spells must not produce absurd minutes."""
    await truncate_all(session)
    await _load_both_fixtures(session)

    rows = (
        await session.execute(
            text(
                """
                select p.name, ps.minutes_played, m.source_id
                from player_match_stats ps
                join players p on p.id = ps.player_id
                join matches m on m.id = ps.match_id
                """
            )
        )
    ).all()

    assert rows
    assert all(row.minutes_played is not None and row.minutes_played >= 0 for row in rows)
    # Nothing exceeds the 124:28 the extra-time final actually ran.
    assert max(row.minutes_played for row in rows) == 124

    # Keyed to the final only: in the quarter-final Di María was an unused substitute.
    final_rows = {row.name: row for row in rows if row.source_id == f"statsbomb:match:{FINAL}"}
    assert final_rows["Ángel Fabián Di María Hernández"].minutes_played == 116  # off at 116:15
    assert final_rows["Giovani Lo Celso"].minutes_played == 28  # on at 96:47, played out
    # He did not feature in the quarter-final, so that row must read zero, not 116.
    qf_rows = {row.name: row for row in rows if row.source_id == f"statsbomb:match:{QUARTER_FINAL}"}
    assert qf_rows["Ángel Fabián Di María Hernández"].minutes_played == 0

    # Every squad member is stored, unused substitutes included (26 + 26 in the group
    # stage squads, 26 + 25 in the final).
    squads = (
        await session.execute(
            text(
                """
                select count(*) as squad
                from player_match_stats ps
                join matches m on m.id = ps.match_id
                group by m.source_id
                """
            )
        )
    ).all()
    assert sorted(row.squad for row in squads) == [51, 52]
