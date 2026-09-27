"""The ETL against the committed real fixtures.

The fixtures are two real 2024 Copa America matches (see docs/data-source.md): the final,
which went to extra time, and a quarter-final that went to penalties. Between them they
cover the two failure modes that would silently corrupt every number downstream --
extra-time events being mishandled, and shootout penalties being counted as goals.

Every expected value here was read straight out of the raw JSON with a separate script,
not copied from the ETL's own output. Where a total can be cross-checked a second way
(for example, team pass counts summing to the match's pass events) the test does that too.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.analytics.counts import aggregate_player, aggregate_team
from app.etl.statsbomb import (
    MAX_PERIOD,
    PlayerAppearance,
    parse_events,
    parse_formations,
    parse_lineups,
    parse_match,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "statsbomb"
FINAL = 3943077  # Argentina 1-0 Colombia, after extra time
QUARTER_FINAL = 3942228  # Argentina 1-1 Ecuador, won on penalties

ARGENTINA = 779
COLOMBIA = 769
ECUADOR = 3565
LAUTARO = 11456  # scored the winner in the final, 111'


def load(kind: str, match_id: int) -> list[dict[str, Any]]:
    with (FIXTURES / kind / f"{match_id}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def load_matches() -> list[dict[str, Any]]:
    with (FIXTURES / "matches" / "223" / "282.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def to_records(parsed: list[Any]) -> list[Any]:
    """Map parsed events onto `EventRecord`s, resolving the ids our own way."""
    return [
        event.to_record(
            team_id=int(event.team_source_id.rsplit(":", 1)[1]),
            player_id=(
                int(event.player_source_id.rsplit(":", 1)[1]) if event.player_source_id else None
            ),
        )
        for event in parsed
    ]


@pytest.mark.parametrize(
    ("match_id", "expected_parsed", "expected_skipped"),
    [
        (FINAL, 4146, 0),
        (QUARTER_FINAL, 2839, 22),
    ],
)
def test_periods_one_to_four_are_parsed_and_shootouts_dropped(
    match_id: int, expected_parsed: int, expected_skipped: int
) -> None:
    raw = load("events", match_id)
    expected_in_play = sum(1 for event in raw if int(event["period"]) <= MAX_PERIOD)

    parsed, skipped = parse_events(raw)

    assert len(parsed) == expected_in_play == expected_parsed
    assert skipped == expected_skipped
    assert len(parsed) + skipped == len(raw)


def test_the_final_had_no_shootout_but_did_have_extra_time() -> None:
    raw = load("events", FINAL)

    assert {event["period"] for event in raw} == {1, 2, 3, 4}
    assert parse_events(raw)[1] == 0


def test_shootout_penalties_are_not_counted_as_goals() -> None:
    """22 period-5 events exist, six of which are penalties scored as 'Goal'.

    Counting every 'Goal' shot would report 8 goals in a 1-1 match.
    """
    raw = load("events", QUARTER_FINAL)
    shootout_goals = [
        event
        for event in raw
        if int(event["period"]) > MAX_PERIOD
        and event["type"]["name"] == "Shot"
        and event["shot"].get("outcome", {}).get("name") == "Goal"
    ]

    assert len(shootout_goals) == 6

    parsed, _ = parse_events(raw)
    regulation_goals = [
        event for event in parsed if event.event_type == "shot" and event.outcome == "Goal"
    ]

    assert len(regulation_goals) == 2


@pytest.mark.parametrize(
    ("match_id", "expected_goals"),
    [(FINAL, 1), (QUARTER_FINAL, 2)],
)
def test_regulation_goals_match_the_source_scoreline(match_id: int, expected_goals: int) -> None:
    raw_match = next(entry for entry in load_matches() if entry["match_id"] == match_id)
    parsed, _ = parse_events(load("events", match_id))

    goals = [event for event in parsed if event.event_type == "shot" and event.outcome == "Goal"]
    scoreline_total = int(raw_match["home_score"]) + int(raw_match["away_score"])

    assert len(goals) == expected_goals == scoreline_total


def test_the_winner_of_the_final_is_lautaros_111th_minute_goal() -> None:
    parsed, _ = parse_events(load("events", FINAL))

    goals = [event for event in parsed if event.event_type == "shot" and event.outcome == "Goal"]

    assert len(goals) == 1
    assert goals[0].minute == 111
    assert goals[0].player_source_id == f"statsbomb:player:{LAUTARO}"
    assert goals[0].xg == pytest.approx(0.19881123, abs=1e-9)


def test_team_aggregates_for_the_final() -> None:
    """Verified by hand from the raw feed: Argentina 11 shots (5 on target), Colombia 19 (4)."""
    parsed, _ = parse_events(load("events", FINAL))
    records = to_records(parsed)

    argentina = aggregate_team(records, ARGENTINA)
    colombia = aggregate_team(records, COLOMBIA)

    assert (argentina.shots, argentina.shots_on_target) == (11, 5)
    assert (colombia.shots, colombia.shots_on_target) == (19, 4)
    assert argentina.xg == pytest.approx(1.0827, abs=1e-3)
    assert colombia.xg == pytest.approx(0.9723, abs=1e-3)
    # The match's 30 shots are fully accounted for by the two teams.
    assert argentina.shots + colombia.shots == 30


def test_team_pass_counts_add_up_to_every_pass_in_the_match() -> None:
    raw = load("events", FINAL)
    expected_passes = sum(1 for event in raw if event["type"]["name"] == "Pass")

    parsed, _ = parse_events(raw)
    records = to_records(parsed)

    argentina = aggregate_team(records, ARGENTINA)
    colombia = aggregate_team(records, COLOMBIA)

    assert (argentina.passes, colombia.passes) == (537, 660)
    assert argentina.passes + colombia.passes == expected_passes == 1197
    assert (argentina.completed_passes, colombia.completed_passes) == (436, 556)
    assert argentina.pass_accuracy == pytest.approx(81.19, abs=0.01)
    assert colombia.pass_accuracy == pytest.approx(84.24, abs=0.01)


def test_tackle_counts_come_from_duel_types() -> None:
    """Argentina made 17 tackle duels and Colombia 24, per the raw feed.

    A tackle has to be identifiable from `event_type` alone, because the schema has no
    duel-type column and Phase 2's PPDA needs to count defensive actions.
    """
    parsed, _ = parse_events(load("events", FINAL))
    tackle_events = [event for event in parsed if event.event_type == "tackle"]

    assert sum(1 for e in tackle_events if e.team_source_id == "statsbomb:team:779") == 17
    assert sum(1 for e in tackle_events if e.team_source_id == "statsbomb:team:769") == 24
    # Aerial duels must not be mistaken for tackles.
    assert any(event.event_type == "aerial_lost" for event in parsed)


def test_lautaro_player_aggregate_matches_the_raw_feed() -> None:
    """Hand-checkable: one player's shots, goals and xG straight from the JSON."""
    raw = load("events", FINAL)
    raw_shots = [
        event
        for event in raw
        if int(event["period"]) <= MAX_PERIOD
        and event["type"]["name"] == "Shot"
        and event.get("player", {}).get("id") == LAUTARO
    ]
    raw_xg = sum(event["shot"]["statsbomb_xg"] for event in raw_shots)

    parsed, _ = parse_events(raw)
    aggregate = aggregate_player(to_records(parsed), LAUTARO)

    assert raw_shots, "expected the winner's shots in the raw feed"
    assert aggregate.shots == len(raw_shots)
    assert aggregate.goals == 1
    assert aggregate.xg == pytest.approx(raw_xg, abs=1e-12)


def test_xg_is_present_on_every_shot() -> None:
    for match_id in (FINAL, QUARTER_FINAL):
        parsed, _ = parse_events(load("events", match_id))
        shots = [event for event in parsed if event.event_type == "shot"]

        assert shots, f"expected shots in match {match_id}"
        assert all(shot.xg is not None for shot in shots)


def test_events_without_a_location_are_kept_with_null_coordinates() -> None:
    """44 events in the final (Half Start/End and friends) have no coordinates."""
    parsed, _ = parse_events(load("events", FINAL))

    assert sum(1 for event in parsed if event.x is None) > 0


def appearances_for(match_id: int) -> list[PlayerAppearance]:
    """Parse a fixture's lineups the way the ETL does, final whistle included."""
    parsed, _ = parse_events(load("events", match_id))
    match_end = max(event.minute * 60 + event.second for event in parsed)
    return parse_lineups(load("lineups", match_id), match_end)


def test_lineups_produce_both_squads_with_extra_time_minutes() -> None:
    appearances = appearances_for(FINAL)

    assert {appearance.team_source_id for appearance in appearances} == {
        "statsbomb:team:779",
        "statsbomb:team:769",
    }
    # The final ran to 124:28, so players who saw it out report 124, not 120.
    assert max(appearance.minutes_played for appearance in appearances) == 124
    assert all(appearance.minutes_played >= 0 for appearance in appearances)
    # Unused substitutes come through with zero, not missing.
    assert min(appearance.minutes_played for appearance in appearances) == 0


def test_lineup_minutes_use_the_appearance_window_not_the_spell_sum() -> None:
    """Both shapes below are taken from the real final; see `parse_lineups`."""
    by_name = {appearance.name: appearance for appearance in appearances_for(FINAL)}

    di_maria = by_name["\u00c1ngel Fabi\u00e1n Di Mar\u00eda Hern\u00e1ndez"]
    assert di_maria.minutes_played == 116  # substituted off at 116:15
    assert di_maria.position_played == "Right Midfield"

    lo_celso = by_name["Giovani Lo Celso"]
    assert lo_celso.minutes_played == 28  # on at 96:47, played out the final whistle
    assert lo_celso.position_played == "Center Defensive Midfield"

    unused = [entry for entry in by_name.values() if entry.minutes_played == 0]
    assert unused and all(entry.position_played is None for entry in unused)


def test_formations_include_both_starting_shapes_and_the_shifts() -> None:
    """The feed stores `formation` as an int (442), and repeats a shape per shift."""
    rows = parse_formations(load("events", FINAL))
    by_team: dict[str, list[str]] = {}
    for row in rows:
        by_team.setdefault(row["team_source_id"], []).append(row["formation_string"])

    # Argentina: 4-4-2 kick-off plus four shifts (two of them re-statements of 4-1-4-1).
    assert by_team["statsbomb:team:779"] == ["4-4-2", "4-4-2", "4-1-4-1", "4-1-4-1", "3-4-3"]
    assert by_team["statsbomb:team:769"] == ["4-1-2-1-2"]
    # The last shift is in extra time (period 4).
    assert rows[-1]["period"] == 4
    assert rows[-1]["start_minute"] == 116
    assert all(row["period"] <= MAX_PERIOD for row in rows)


def test_match_metadata_matches_the_fixture_file() -> None:
    raw_match = next(entry for entry in load_matches() if entry["match_id"] == FINAL)

    row = parse_match(raw_match)

    assert row["source_id"] == f"statsbomb:match:{FINAL}"
    assert row["competition"] == "Copa America"
    assert row["season"] == "2024"
    assert row["home_team_name"] == "Argentina"
    assert row["away_team_name"] == "Colombia"
    assert (row["home_score"], row["away_score"]) == (1, 0)
    assert str(row["match_date"]) == "2024-07-15"


def test_quarter_final_teams_are_argentina_and_ecuador() -> None:
    raw_match = next(entry for entry in load_matches() if entry["match_id"] == QUARTER_FINAL)

    row = parse_match(raw_match)

    assert row["away_team_source_id"] == f"statsbomb:team:{ECUADOR}"
    assert (row["home_score"], row["away_score"]) == (1, 1)
