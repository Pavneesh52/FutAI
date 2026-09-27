"""Tests for the ETL's parsing helpers, using shapes copied from the real feed."""

from __future__ import annotations

import pytest
from app.etl.statsbomb import (
    MAX_PERIOD,
    event_outcome,
    event_xg,
    normalise_event_type,
    parse_events,
    parse_lineups,
    parse_match,
    parse_minutes,
    slugify,
    source_id,
    substitution_windows,
    type_payload,
)

UUID = "d898763d-eb70-4552-93d3-6f8631ddbcc9"


def test_source_id_is_provider_tagged() -> None:
    assert source_id("event", UUID) == f"statsbomb:event:{UUID}"
    assert source_id("team", 779) == "statsbomb:team:779"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pass", "pass"),
        ("Ball Receipt*", "ball_receipt"),
        ("50/50", "fifty_fifty"),
        ("Starting XI", "starting_xi"),
        ("Goal Keeper", "goal_keeper"),
        ("Referee Ball-Drop", "referee_ball_drop"),
        ("Player Off", "player_off"),
        ("Own Goal For", "own_goal_for"),
        ("Own Goal Against", "own_goal_against"),
        ("Bad Behaviour", "bad_behaviour"),
        ("Shot", "shot"),
    ],
)
def test_event_types_are_normalised(raw: str, expected: str) -> None:
    assert normalise_event_type(raw, {"type": {"name": raw}}) == expected


def test_duel_is_split_by_duel_type_so_tackles_are_identifiable() -> None:
    tackle = {"type": {"name": "Duel"}, "duel": {"type": {"name": "Tackle"}}}
    aerial = {"type": {"name": "Duel"}, "duel": {"type": {"name": "Aerial Lost"}}}
    unknown = {"type": {"name": "Duel"}, "duel": {}}

    assert normalise_event_type("Duel", tackle) == "tackle"
    assert normalise_event_type("Duel", aerial) == "aerial_lost"
    assert normalise_event_type("Duel", unknown) == "duel"


def test_slugify_never_returns_an_empty_string() -> None:
    assert slugify("!!!") == ""
    assert normalise_event_type("!!!", {"type": {"name": "!!!"}}) == "unknown"


def test_type_payload_finds_the_single_extra_dict() -> None:
    event = {
        "id": UUID,
        "index": 1,
        "period": 1,
        "minute": 0,
        "second": 0,
        "type": {"id": 30, "name": "Pass"},
        "possession": 2,
        "possession_team": {"id": 779},
        "play_pattern": {"id": 1},
        "team": {"id": 779},
        "location": [61.0, 40.1],
        "related_events": [],
        "pass": {"length": 10.0, "recipient": {"id": 1}},
    }

    assert type_payload(event) == {"length": 10.0, "recipient": {"id": 1}}


def test_type_payload_is_none_when_there_is_no_payload() -> None:
    assert type_payload({"id": UUID, "type": {"name": "Half Start"}, "minute": 0}) is None


def test_completed_pass_has_no_outcome_key_and_is_recorded_as_complete() -> None:
    """Verified in the feed: a successful pass simply has no `outcome`."""
    completed = {"type": {"name": "Pass"}, "pass": {"length": 5.0}}
    incomplete = {
        "type": {"name": "Pass"},
        "pass": {"outcome": {"id": 9, "name": "Incomplete"}},
    }

    assert event_outcome(completed) == "Complete"
    assert event_outcome(incomplete) == "Incomplete"


def test_pass_offside_and_unknown_are_not_recorded_as_complete() -> None:
    for name in ("Pass Offside", "Unknown", "Out"):
        event = {"type": {"name": "Pass"}, "pass": {"outcome": {"name": name}}}
        assert event_outcome(event) == name


def test_shot_outcome_and_xg_are_extracted() -> None:
    event = {
        "type": {"name": "Shot"},
        "shot": {"outcome": {"name": "Saved"}, "statsbomb_xg": 0.07213958},
    }

    assert event_outcome(event) == "Saved"
    assert event_xg(event) == pytest.approx(0.07213958)


def test_xg_is_none_for_non_shots() -> None:
    assert event_xg({"type": {"name": "Pass"}, "pass": {}}) is None


def test_minutes_parsing_handles_extra_time() -> None:
    assert parse_minutes("00:00") == 0
    assert parse_minutes("45:30") == 45 * 60 + 30
    assert parse_minutes("116:15") == 116 * 60 + 15  # extra time goes past 90
    assert parse_minutes(None) is None
    assert parse_minutes("nonsense") is None


def _raw_event(
    *,
    event_type: str = "Pass",
    period: int = 1,
    payload: dict[str, object] | None = None,
    include_player: bool = True,
    related: list[str] | None = None,
    location: list[float] | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "id": UUID,
        "index": 1,
        "period": period,
        "timestamp": "00:00:00.000",
        "minute": 10,
        "second": 5,
        "type": {"id": 30, "name": event_type},
        "possession": 17,
        "possession_team": {"id": 779, "name": "Argentina"},
        "play_pattern": {"id": 1, "name": "Regular Play"},
        "team": {"id": 779, "name": "Argentina"},
        "related_events": related or [],
    }
    if include_player:
        event["player"] = {"id": 5503, "name": "Lionel Andres Messi Cuccittini"}
    if location is not None:
        event["location"] = location
    event_key = event_type.lower().replace(" ", "_").replace("*", "")
    if payload is not None:
        event[event_key] = payload
    return event


def test_parse_events_drops_penalty_shootout_events() -> None:
    """Period 5 is a shootout; `home_score`/`away_score` exclude it."""
    events = [
        _raw_event(period=1),
        _raw_event(period=4),
        _raw_event(period=MAX_PERIOD + 1, event_type="Shot", payload={"outcome": {"name": "Goal"}}),
    ]

    parsed, skipped = parse_events(events)

    assert len(parsed) == 2
    assert skipped == 1
    assert all(event.period <= MAX_PERIOD for event in parsed)


def test_parse_events_tolerates_missing_location_and_player() -> None:
    parsed, _ = parse_events([_raw_event(include_player=False)])

    assert parsed[0].x is None
    assert parsed[0].y is None
    assert parsed[0].player_source_id is None


def test_parse_events_extracts_coordinates_and_possession() -> None:
    parsed, _ = parse_events([_raw_event(location=[61.0, 40.1])])

    assert (parsed[0].x, parsed[0].y) == (61.0, 40.1)
    assert parsed[0].possession_id == 17


def test_parse_events_keeps_only_the_first_related_event() -> None:
    """`related_event_id` is a single column (Appendix A), so the first id wins."""
    parsed, _ = parse_events([_raw_event(related=[UUID, "another-uuid"])])

    assert parsed[0].related_source_id == f"statsbomb:event:{UUID}"
    assert parse_events([_raw_event(related=[])])[0][0].related_source_id is None


def test_parse_events_reads_the_goal_assist_flag() -> None:
    parsed, _ = parse_events([_raw_event(payload={"goal_assist": True})])

    assert parsed[0].is_goal_assist is True
    assert parse_events([_raw_event(payload={})])[0][0].is_goal_assist is False


def test_parse_events_to_record_maps_surrogate_ids() -> None:
    parsed, _ = parse_events([_raw_event(location=[10.0, 20.0])])

    record = parsed[0].to_record(team_id=42, player_id=7)

    assert record.team_id == 42
    assert record.player_id == 7
    assert record.x == 10.0


def _lineup(*positions: dict[str, object], player_id: int = 5503) -> list[dict[str, object]]:
    return [
        {
            "team_id": 779,
            "team_name": "Argentina",
            "lineup": [
                {
                    "player_id": player_id,
                    "player_name": "Lionel Andres Messi Cuccittini",
                    "positions": list(positions),
                }
            ],
        }
    ]


def test_parse_lineups_measures_the_appearance_window_once() -> None:
    """Spells are contiguous, so the window length must not double-count the overlap."""
    raw = _lineup(
        {"position": "Right Wing", "from": "00:00", "to": "65:00"},
        {"position": "Center Forward", "from": "65:00", "to": "120:00"},
    )

    appearances = parse_lineups(raw, match_end_seconds=120 * 60)

    assert len(appearances) == 1
    assert appearances[0].minutes_played == 120
    # The longest spell wins: 65 minutes at right wing beats 55 at centre forward.
    assert appearances[0].position_played == "Right Wing"


def test_parse_lineups_prefers_the_substitution_over_a_final_whistle_spell() -> None:
    """Real shape (Di Maria, final): a null-`to` spell sits inside a substituted-off run."""
    raw = _lineup(
        {
            "position": "Right Midfield",
            "from": "00:00",
            "to": "116:15",
            "end_reason": "Substitution - Off (Tactical)",
        },
        {
            "position": "Left Midfield",
            "from": "16:08",
            "to": "66:26",
            "end_reason": "Tactical Shift",
        },
        {
            "position": "Right Midfield",
            "from": "66:26",
            "to": None,
            "end_reason": "Final Whistle",
        },
    )

    appearances = parse_lineups(raw, match_end_seconds=124 * 60 + 28)

    # 116:15, not the 124:28 final whistle: the player left the pitch early.
    assert appearances[0].minutes_played == 116
    assert appearances[0].position_played == "Right Midfield"


def test_parse_lineups_handles_a_reversed_spell_for_a_late_substitute() -> None:
    """Real shape (Lo Celso, final): the first spell runs backwards, the last is open."""
    raw = _lineup(
        {
            "position": "Center Defensive Midfield",
            "from": "116:37",
            "to": "96:47",
            "end_reason": "Tactical Shift",
        },
        {
            "position": "Center Back",
            "from": "96:47",
            "to": "96:47",
            "end_reason": "Tactical Shift",
        },
        {
            "position": "Center Defensive Midfield",
            "from": "96:47",
            "to": None,
            "end_reason": "Final Whistle",
        },
    )

    appearances = parse_lineups(raw, match_end_seconds=124 * 60 + 28)

    # On at 96:47, still on at the final whistle: ~28 minutes, not zero.
    assert appearances[0].minutes_played == 28
    assert appearances[0].position_played == "Center Defensive Midfield"


def test_parse_lineups_keeps_unused_substitutes_at_zero_minutes() -> None:
    raw = _lineup(player_id=1)

    appearances = parse_lineups(raw, match_end_seconds=90 * 60)

    assert appearances[0].minutes_played == 0
    assert appearances[0].position_played is None


def test_substitution_windows_reads_both_sides_of_the_swap() -> None:
    """`player` leaves at the clock, `substitution.replacement` comes on at it."""
    raw_events = [
        _raw_event(),  # a non-substitution event must be ignored
        {
            "id": "a-86f2",
            "type": {"name": "Substitution"},
            "period": 2,
            "minute": 96,
            "second": 3,
            "team": {"id": 779, "name": "Argentina"},
            "player": {"id": 31053, "name": "Julian Alvarez"},
            "substitution": {"replacement": {"id": 5503, "name": "Lautaro Martinez"}},
        },
    ]

    windows = substitution_windows(raw_events)

    assert windows[5503] == (96 * 60 + 3, None)  # came on, not yet taken off
    assert windows[31053] == (None, 96 * 60 + 3)  # went off


def test_parse_lineups_recovers_a_missing_entry_spell_from_the_events() -> None:
    """Real shape (Lautaro Martinez, final): the feed never recorded his 96:03 entry.

    The only spell starts at the 116:37 tactical shift, so the lineups file alone would
    report 8 minutes for a player who scored in the 111th. The substitution events are
    exact and complete: on at 96:03, never taken off, so 28 minutes to the 124:28 whistle.
    """
    raw = _lineup(
        {
            "position": "Center Forward",
            "from": "116:37",
            "to": None,
            "end_reason": "Final Whistle",
        },
        player_id=5503,
    )
    sub_windows = {5503: (96 * 60 + 3, None)}

    appearances = parse_lineups(raw, match_end_seconds=124 * 60 + 28, sub_windows=sub_windows)

    assert appearances[0].minutes_played == 28
    assert appearances[0].position_played == "Center Forward"


def test_parse_lineups_widens_a_rounded_exit_with_the_event_clock() -> None:
    """The spells round to the minute; the events carry seconds. Widen, never shrink."""
    raw = _lineup(
        {
            "position": "Center Back",
            "from": "00:00",
            "to": "116:37",
            "end_reason": "Substitution - Off (Tactical)",
        }
    )
    # Came off at 116:37 per the spell, but the swap event says 116:51.
    sub_windows = {5503: (None, 116 * 60 + 51)}

    appearances = parse_lineups(raw, match_end_seconds=124 * 60 + 28, sub_windows=sub_windows)

    assert appearances[0].minutes_played == 117


def test_parse_lineups_closes_an_open_spell_at_the_match_end() -> None:
    raw = _lineup(
        {"position": "Left Back", "from": "00:00", "to": None, "end_reason": "Final Whistle"}
    )

    appearances = parse_lineups(raw, match_end_seconds=97 * 60 + 51)

    # A player on from kick-off to the 97:51 final whistle played 98 minutes.
    assert appearances[0].minutes_played == 98


def test_parse_match_reads_the_top_level_scores() -> None:
    """`home_score` is top level; the team objects only hold id/name/country."""
    raw = {
        "match_id": 3943077,
        "match_date": "2024-07-15",
        "competition": {"competition_id": 223, "competition_name": "Copa America"},
        "season": {"season_id": 282, "season_name": "2024"},
        "home_team": {
            "home_team_id": 779,
            "home_team_name": "Argentina",
            "country": {"id": 11, "name": "Argentina"},
        },
        "away_team": {
            "away_team_id": 769,
            "away_team_name": "Colombia",
            "country": {"id": 49, "name": "Colombia"},
        },
        "home_score": 1,
        "away_score": 0,
    }

    row = parse_match(raw)

    assert row["source_id"] == "statsbomb:match:3943077"
    assert row["home_score"] == 1
    assert row["away_score"] == 0
    assert row["competition"] == "Copa America"
    assert row["season"] == "2024"
    assert row["home_team_source_id"] == "statsbomb:team:779"
    assert row["home_team_country"] == "Argentina"
    assert str(row["match_date"]) == "2024-07-15"


def test_parse_match_keeps_missing_scores_as_none() -> None:
    raw = {
        "match_id": 1,
        "match_date": "2024-01-01",
        "competition": {"competition_name": "Test"},
        "season": {"season_name": "2024"},
        "home_team": {"home_team_id": 1, "home_team_name": "A"},
        "away_team": {"away_team_id": 2, "away_team_name": "B"},
    }

    row = parse_match(raw)

    assert row["home_score"] is None
    assert row["away_score"] is None
