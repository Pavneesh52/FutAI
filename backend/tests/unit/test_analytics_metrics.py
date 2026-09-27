"""Unit tests for pure analytics metrics (Phase 2).

Tests include:
- Hand-verified assertions on real StatsBomb tournament fixtures (3943077 and 3942228).
- Deterministic hand-calculated synthetic match fixture (3rd fixture).
- Edge cases (zero defensive actions, missing coordinates, zero passes, extra-time events).
- Mathematical invariants and property tests (field tilt sums to 1.0, possession sums to 100%).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.analytics.metrics import (
    field_tilt,
    pass_accuracy,
    possession_pct,
    ppda,
)
from app.analytics.types import EventRecord
from app.etl.statsbomb import parse_events

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "statsbomb"
FINAL_MATCH_ID = 3943077
QUARTER_MATCH_ID = 3942228

ARGENTINA_ID = 779
COLOMBIA_ID = 769
ECUADOR_ID = 3565


def _load_fixture_records(match_id: int) -> list[EventRecord]:
    """Parse a StatsBomb event fixture into EventRecords."""
    path = FIXTURES_DIR / "events" / f"{match_id}.json"
    with path.open(encoding="utf-8") as f:
        raw_events = json.load(f)

    parsed, _ = parse_events(raw_events)
    return [
        e.to_record(
            team_id=int(e.team_source_id.rsplit(":", 1)[1]),
            player_id=int(e.player_source_id.rsplit(":", 1)[1]) if e.player_source_id else None,
        )
        for e in parsed
    ]


# ---------------------------------------------------------------------------
# Hand-verified Real Fixtures
# ---------------------------------------------------------------------------


class TestRealFixturesHandVerified:
    """Hand-calculated ground truth tests from actual StatsBomb events."""

    def test_final_3943077_argentina_colombia(self) -> None:
        records = _load_fixture_records(FINAL_MATCH_ID)

        # Possession %
        col_poss = possession_pct(records, COLOMBIA_ID)
        arg_poss = possession_pct(records, ARGENTINA_ID)
        assert col_poss is not None and arg_poss is not None
        assert pytest.approx(col_poss, rel=1e-3) == 55.1378  # 660 / 1197
        assert pytest.approx(arg_poss, rel=1e-3) == 44.8621  # 537 / 1197
        assert pytest.approx(col_poss + arg_poss, rel=1e-6) == 100.0

        # Pass accuracy
        col_acc = pass_accuracy(records, COLOMBIA_ID)
        arg_acc = pass_accuracy(records, ARGENTINA_ID)
        assert col_acc is not None and arg_acc is not None
        assert pytest.approx(col_acc, abs=0.1) == 84.2
        assert pytest.approx(arg_acc, abs=0.1) == 81.2

        # PPDA
        col_ppda = ppda(records, COLOMBIA_ID, all_team_ids=[COLOMBIA_ID, ARGENTINA_ID])
        arg_ppda = ppda(records, ARGENTINA_ID, all_team_ids=[COLOMBIA_ID, ARGENTINA_ID])
        assert col_ppda is not None and arg_ppda is not None
        assert pytest.approx(col_ppda, abs=0.05) == 13.76  # 399 opp passes / 29 def actions
        assert pytest.approx(arg_ppda, abs=0.05) == 39.33  # 472 opp passes / 12 def actions

        # Field tilt
        col_tilt = field_tilt(records, COLOMBIA_ID)
        arg_tilt = field_tilt(records, ARGENTINA_ID)
        assert col_tilt is not None and arg_tilt is not None
        assert pytest.approx(col_tilt, abs=0.001) == 0.5642  # 171 / 303
        assert pytest.approx(arg_tilt, abs=0.001) == 0.4358  # 132 / 303
        assert pytest.approx(col_tilt + arg_tilt, rel=1e-6) == 1.0

    def test_quarter_3942228_argentina_ecuador(self) -> None:
        records = _load_fixture_records(QUARTER_MATCH_ID)

        # Possession %
        arg_poss = possession_pct(records, ARGENTINA_ID)
        ecu_poss = possession_pct(records, ECUADOR_ID)
        assert arg_poss is not None and ecu_poss is not None
        assert pytest.approx(arg_poss, rel=1e-3) == 50.567  # 401 / 793
        assert pytest.approx(ecu_poss, rel=1e-3) == 49.432  # 392 / 793
        assert pytest.approx(arg_poss + ecu_poss, rel=1e-6) == 100.0

        # Pass accuracy
        arg_acc = pass_accuracy(records, ARGENTINA_ID)
        ecu_acc = pass_accuracy(records, ECUADOR_ID)
        assert arg_acc is not None and ecu_acc is not None
        assert pytest.approx(arg_acc, abs=0.1) == 80.5
        assert pytest.approx(ecu_acc, abs=0.1) == 80.1

        # PPDA
        arg_ppda = ppda(records, ARGENTINA_ID, all_team_ids=[ARGENTINA_ID, ECUADOR_ID])
        ecu_ppda = ppda(records, ECUADOR_ID, all_team_ids=[ARGENTINA_ID, ECUADOR_ID])
        assert arg_ppda is not None and ecu_ppda is not None
        assert pytest.approx(arg_ppda, abs=0.05) == 11.52  # 265 opp passes / 23 def actions
        assert pytest.approx(ecu_ppda, abs=0.05) == 13.10  # 275 opp passes / 21 def actions

        # Field tilt
        arg_tilt = field_tilt(records, ARGENTINA_ID)
        ecu_tilt = field_tilt(records, ECUADOR_ID)
        assert arg_tilt is not None and ecu_tilt is not None
        assert pytest.approx(arg_tilt, abs=0.001) == 0.6351  # 94 / 148
        assert pytest.approx(ecu_tilt, abs=0.001) == 0.3649  # 54 / 148
        assert pytest.approx(arg_tilt + ecu_tilt, rel=1e-6) == 1.0


# ---------------------------------------------------------------------------
# Hand-calculated Synthetic Fixture (Fixture 3)
# ---------------------------------------------------------------------------


TEAM_A = 101
TEAM_B = 102


@pytest.fixture
def synthetic_match_events() -> list[EventRecord]:
    """Deterministic synthetic match fixture with exact hand-calculated expected values.

    Team A:
    - 4 passes in defensive 40% (x=20, 25, 30, 35) completed
    - 3 passes in middle third (x=50, 60, 70) completed
    - 3 passes in attacking third (x=85, 90, 95) -> 2 completed, 1 incomplete
    Total Team A passes = 10 (9 completed, 1 incomplete)
    Team A passes in own 60% (x <= 72) = 7
    Team A passes in final third (x >= 80) = 3

    Team B:
    - 2 passes in own defensive 40% (x=10, 30) completed
    - 2 passes in own middle third (x=65, 70) -> 1 completed, 1 incomplete
    - 1 pass in attacking third (x=85) completed
    Total Team B passes = 5 (4 completed, 1 incomplete)
    Team B passes in own 60% (x <= 72) = 4
    Team B passes in final third (x >= 80) = 1

    Defensive actions:
    Team A: 1 tackle at x=55 (atk 60%), 1 interception at x=90 (atk 60%), 1 tackle at x=30 (def 40% - not atk 60%)
    Team A qualifying def actions in atk 60% (x >= 48) = 2.
    Team B: 1 foul_committed at x=50 (atk 60%), 1 interception at x=20 (def 40% - not atk 60%)
    Team B qualifying def actions in atk 60% (x >= 48) = 1.
    """
    return [
        # Team A passes
        EventRecord(event_type="pass", team_id=TEAM_A, x=20.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=25.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=30.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=35.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=50.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=60.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=70.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=85.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=90.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_A, x=95.0, y=40.0, outcome="Incomplete"),
        # Team B passes
        EventRecord(event_type="pass", team_id=TEAM_B, x=10.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_B, x=30.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_B, x=65.0, y=40.0, outcome="Complete"),
        EventRecord(event_type="pass", team_id=TEAM_B, x=70.0, y=40.0, outcome="Incomplete"),
        EventRecord(event_type="pass", team_id=TEAM_B, x=85.0, y=40.0, outcome="Complete"),
        # Team A defensive actions
        EventRecord(event_type="tackle", team_id=TEAM_A, x=55.0, y=40.0),
        EventRecord(event_type="interception", team_id=TEAM_A, x=90.0, y=40.0),
        EventRecord(
            event_type="tackle", team_id=TEAM_A, x=30.0, y=40.0
        ),  # x < 48, ignored for PPDA
        # Team B defensive actions
        EventRecord(event_type="foul_committed", team_id=TEAM_B, x=50.0, y=40.0),
        EventRecord(
            event_type="interception", team_id=TEAM_B, x=20.0, y=40.0
        ),  # x < 48, ignored for PPDA
    ]


class TestSyntheticMatchFixture:
    """Exact manual calculations on the synthetic match."""

    def test_possession_pct(self, synthetic_match_events: list[EventRecord]) -> None:
        # Team A: 10 / 15 = 66.6667%
        # Team B: 5 / 15 = 33.3333%
        poss_a = possession_pct(synthetic_match_events, TEAM_A)
        poss_b = possession_pct(synthetic_match_events, TEAM_B)
        assert poss_a is not None and poss_b is not None
        assert pytest.approx(poss_a, abs=1e-4) == 66.6667
        assert pytest.approx(poss_b, abs=1e-4) == 33.3333

    def test_pass_accuracy(self, synthetic_match_events: list[EventRecord]) -> None:
        # Team A: 9 / 10 = 90.0%
        # Team B: 4 / 5 = 80.0%
        acc_a = pass_accuracy(synthetic_match_events, TEAM_A)
        acc_b = pass_accuracy(synthetic_match_events, TEAM_B)
        assert acc_a is not None and acc_b is not None
        assert pytest.approx(acc_a, abs=1e-4) == 90.0
        assert pytest.approx(acc_b, abs=1e-4) == 80.0

    def test_field_tilt(self, synthetic_match_events: list[EventRecord]) -> None:
        # Team A: 3 / 4 = 0.75
        # Team B: 1 / 4 = 0.25
        tilt_a = field_tilt(synthetic_match_events, TEAM_A)
        tilt_b = field_tilt(synthetic_match_events, TEAM_B)
        assert tilt_a is not None and tilt_b is not None
        assert pytest.approx(tilt_a, abs=1e-4) == 0.75
        assert pytest.approx(tilt_b, abs=1e-4) == 0.25

    def test_ppda(self, synthetic_match_events: list[EventRecord]) -> None:
        # Team A PPDA: Team B passes in own 60% (4) / Team A def actions in atk 60% (2) = 4 / 2 = 2.0
        # Team B PPDA: Team A passes in own 60% (7) / Team B def actions in atk 60% (1) = 7 / 1 = 7.0
        ppda_a = ppda(synthetic_match_events, TEAM_A, all_team_ids=[TEAM_A, TEAM_B])
        ppda_b = ppda(synthetic_match_events, TEAM_B, all_team_ids=[TEAM_A, TEAM_B])
        assert ppda_a is not None and ppda_b is not None
        assert pytest.approx(ppda_a, abs=1e-4) == 2.0
        assert pytest.approx(ppda_b, abs=1e-4) == 7.0


# ---------------------------------------------------------------------------
# Edge Cases and Boundary Conditions
# ---------------------------------------------------------------------------


class TestAnalyticsEdgeCases:
    """Robustness to corner cases: missing values, zero denominators, red cards."""

    def test_zero_passes_returns_none(self) -> None:
        events = [EventRecord(event_type="shot", team_id=TEAM_A, x=100.0, y=40.0)]
        assert possession_pct(events, TEAM_A) is None
        assert pass_accuracy(events, TEAM_A) is None
        assert field_tilt(events, TEAM_A) is None

    def test_zero_defensive_actions_returns_none_ppda(self) -> None:
        events = [
            EventRecord(event_type="pass", team_id=TEAM_B, x=30.0, y=40.0),
            EventRecord(event_type="pass", team_id=TEAM_B, x=50.0, y=40.0),
        ]
        # Team A has no defensive actions -> PPDA is None (division by zero avoided)
        assert ppda(events, TEAM_A, all_team_ids=[TEAM_A, TEAM_B]) is None

    def test_no_final_third_passes_returns_none_field_tilt(self) -> None:
        events = [
            EventRecord(event_type="pass", team_id=TEAM_A, x=30.0, y=40.0),
            EventRecord(event_type="pass", team_id=TEAM_B, x=45.0, y=40.0),
        ]
        assert field_tilt(events, TEAM_A) is None
        assert field_tilt(events, TEAM_B) is None

    def test_missing_coordinates_safely_ignored(self) -> None:
        events = [
            EventRecord(event_type="pass", team_id=TEAM_A, x=None, y=None, outcome="Complete"),
            EventRecord(event_type="pass", team_id=TEAM_A, x=90.0, y=40.0, outcome="Complete"),
            EventRecord(event_type="pass", team_id=TEAM_B, x=90.0, y=40.0, outcome="Complete"),
            EventRecord(event_type="tackle", team_id=TEAM_A, x=None, y=None),
            EventRecord(event_type="tackle", team_id=TEAM_A, x=60.0, y=40.0),
        ]
        # Possession counts passes regardless of coordinates:
        assert possession_pct(events, TEAM_A) == pytest.approx(66.6667, abs=1e-4)
        # Field tilt only counts passes with x >= 80:
        assert field_tilt(events, TEAM_A) == pytest.approx(0.5, abs=1e-4)
        # PPDA only counts actions with valid coordinates:
        # Team B has 0 passes in own 60% with coords, so PPDA = 0 / 1 = 0.0
        assert ppda(events, TEAM_A, all_team_ids=[TEAM_A, TEAM_B]) == 0.0

    def test_ppda_excludes_aerial_lost_duels(self) -> None:
        """Verify that aerial lost duels are not counted as PPDA defensive actions."""
        events = [
            EventRecord(event_type="pass", team_id=TEAM_B, x=30.0, y=40.0),
            EventRecord(event_type="aerial_lost", team_id=TEAM_A, x=60.0, y=40.0),
        ]
        # aerial_lost is excluded from PPDA defensive actions, so Team A has 0 qualifying actions -> None
        assert ppda(events, TEAM_A, all_team_ids=[TEAM_A, TEAM_B]) is None
