"""Unit tests for possession sequences analysis (Phase 2)."""

from __future__ import annotations

from app.analytics.sequences import possession_sequences
from app.analytics.types import EventRecord

TEAM_A = 101
TEAM_B = 102


def test_possession_sequences_basic() -> None:
    events = [
        # Sequence 1: Team A build up from defensive third to attacking third ending in a shot
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=20.0, y=40.0, minute=10, second=5
        ),
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=55.0, y=40.0, minute=10, second=15
        ),
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=85.0, y=40.0, minute=10, second=25
        ),
        EventRecord(
            event_type="shot", team_id=TEAM_A, possession_id=1, x=95.0, y=40.0, minute=10, second=30
        ),
        # Sequence 2: Team B short sequence in middle third
        EventRecord(
            event_type="pass", team_id=TEAM_B, possession_id=2, x=45.0, y=30.0, minute=11, second=0
        ),
        EventRecord(
            event_type="pass", team_id=TEAM_B, possession_id=2, x=65.0, y=30.0, minute=11, second=10
        ),
    ]

    seqs = possession_sequences(events)
    assert len(seqs) == 2

    # Seq 1 assertions
    s1 = seqs[0]
    assert s1.possession_id == 1
    assert s1.team_id == TEAM_A
    assert s1.start_zone == "defensive_third"
    assert s1.end_zone == "attacking_third"
    assert s1.pass_count == 3
    assert s1.ended_in_shot is True
    assert s1.duration_seconds == 25  # 10:05 to 10:30

    # Seq 2 assertions
    s2 = seqs[1]
    assert s2.possession_id == 2
    assert s2.team_id == TEAM_B
    assert s2.start_zone == "middle_third"
    assert s2.end_zone == "middle_third"
    assert s2.pass_count == 2
    assert s2.ended_in_shot is False
    assert s2.duration_seconds == 10  # 11:00 to 11:10


def test_possession_sequences_single_event_duration() -> None:
    events = [
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=50.0, y=40.0, minute=5, second=20
        ),
    ]
    seqs = possession_sequences(events)
    assert len(seqs) == 1
    assert seqs[0].duration_seconds == 0
    assert seqs[0].start_zone == "middle_third"
    assert seqs[0].end_zone == "middle_third"
    assert seqs[0].pass_count == 1
    assert seqs[0].ended_in_shot is False


def test_possession_sequences_missing_coordinates() -> None:
    events = [
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=None, y=None, minute=5, second=0
        ),
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=None, y=None, minute=5, second=10
        ),
    ]
    seqs = possession_sequences(events)
    assert len(seqs) == 1
    assert seqs[0].start_zone is None
    assert seqs[0].end_zone is None
    assert seqs[0].duration_seconds == 10
    assert seqs[0].pass_count == 2


def test_possession_sequences_skips_none_possession_id() -> None:
    events = [
        EventRecord(
            event_type="starting_xi", team_id=TEAM_A, possession_id=None, minute=0, second=0
        ),
        EventRecord(
            event_type="half_start", team_id=TEAM_A, possession_id=None, minute=0, second=0
        ),
        EventRecord(
            event_type="pass", team_id=TEAM_A, possession_id=1, x=20.0, y=40.0, minute=0, second=1
        ),
    ]
    seqs = possession_sequences(events)
    assert len(seqs) == 1
    assert seqs[0].possession_id == 1
