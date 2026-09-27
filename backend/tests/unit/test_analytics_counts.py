"""Tests for `app.analytics.counts`. No database, no network, no LLM."""

from __future__ import annotations

import pytest
from app.analytics.counts import (
    COMPLETED_PASS_OUTCOME,
    aggregate_player,
    aggregate_team,
    format_formation,
)
from app.analytics.types import EventRecord

HOME = 1
AWAY = 2


def shot(team_id: int, outcome: str, xg: float, player_id: int | None = None) -> EventRecord:
    return EventRecord(
        event_type="shot", team_id=team_id, player_id=player_id, outcome=outcome, xg=xg
    )


def pass_event(
    team_id: int, completed: bool = True, player_id: int | None = None, assist: bool = False
) -> EventRecord:
    return EventRecord(
        event_type="pass",
        team_id=team_id,
        player_id=player_id,
        outcome=COMPLETED_PASS_OUTCOME if completed else "Incomplete",
        is_goal_assist=assist,
    )


def test_team_totals_count_shots_passes_and_xg() -> None:
    events = [
        shot(HOME, "Goal", 0.5),
        shot(HOME, "Saved", 0.1),
        shot(HOME, "Blocked", 0.2),
        shot(AWAY, "Goal", 0.3),
        pass_event(HOME, completed=True),
        pass_event(HOME, completed=False),
        pass_event(AWAY, completed=True),
    ]

    totals = aggregate_team(events, HOME)

    assert totals.shots == 3
    assert totals.shots_on_target == 2  # Goal + Saved; Blocked is not on target
    assert totals.xg == pytest.approx(0.8)
    assert totals.passes == 2
    assert totals.completed_passes == 1
    assert totals.pass_accuracy == pytest.approx(50.0)


def test_post_is_not_on_target() -> None:
    """The Phase 2 definition lists goal/saved/saved-to-post; woodwork is excluded."""
    totals = aggregate_team([shot(HOME, "Post", 0.4)], HOME)

    assert totals.shots == 1
    assert totals.shots_on_target == 0


def test_only_the_requested_team_is_counted() -> None:
    totals = aggregate_team([shot(AWAY, "Goal", 9.9)], HOME)

    assert totals.shots == 0
    assert totals.xg == 0.0


def test_team_without_passes_reports_no_accuracy_rather_than_zero() -> None:
    """A missing measurement must not look like a measured 0%."""
    totals = aggregate_team([], HOME)

    assert totals.passes == 0
    assert totals.pass_accuracy is None


def test_empty_event_list_is_safe() -> None:
    totals = aggregate_team([], HOME)

    assert (totals.shots, totals.shots_on_target, totals.xg) == (0, 0, 0.0)


def test_player_totals_include_goals_assists_shots_and_tackles() -> None:
    striker = 10
    other = 11
    events = [
        shot(HOME, "Goal", 0.4, player_id=striker),
        shot(HOME, "Off T", 0.1, player_id=striker),
        shot(HOME, "Goal", 0.9, player_id=other),
        pass_event(HOME, completed=True, player_id=other, assist=True),
        pass_event(HOME, completed=False, player_id=other),
        EventRecord(event_type="tackle", team_id=HOME, player_id=other, outcome="Won"),
        EventRecord(event_type="tackle", team_id=HOME, player_id=other, outcome="Lost In Play"),
    ]

    totals = aggregate_player(events, other)

    assert totals.goals == 1
    assert totals.shots == 1
    assert totals.assists == 1
    assert totals.tackles == 2
    assert totals.passes == 2
    assert totals.pass_accuracy == pytest.approx(50.0)


def test_player_goals_ignore_other_players() -> None:
    totals = aggregate_player([shot(HOME, "Goal", 0.4, player_id=10)], 99)

    assert totals.goals == 0
    assert totals.shots == 0


def test_player_with_no_passes_reports_no_accuracy() -> None:
    assert aggregate_player([], 10).pass_accuracy is None


def test_an_own_goal_is_not_credited_to_the_player_who_scored_it() -> None:
    """Ecuador 3-1 Jamaica (match 3939980) has the season's only own goal.

    StatsBomb emits it as a pair at the same minute: `Own Goal Against` on the scorer's
    own team (with the player) and `Own Goal For` on the team that is credited with the
    goal (without one). Counting the `Own Goal Against` event for its player would hand
    a defender a goal he put into his own net.
    """
    own_goal_scorer = 10
    events = [
        EventRecord(event_type="own_goal_against", team_id=AWAY, player_id=own_goal_scorer),
        EventRecord(event_type="own_goal_for", team_id=HOME, player_id=None),
        shot(HOME, "Goal", 0.4, player_id=11),
    ]

    assert aggregate_player(events, own_goal_scorer).goals == 0
    # The credited team's goals come from its shots plus its `own_goal_for` events, so a
    # side's tally can exceed its shot total.
    assert aggregate_team(events, HOME).shots == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (442, "4-4-2"),
        (433, "4-3-3"),
        (41212, "4-1-2-1-2"),
        (4231, "4-2-3-1"),
        ("352", "3-5-2"),
        ("4-4-2", "4-4-2"),  # already rendered: passed through, not mangled
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_formation_rendering(raw: object, expected: str | None) -> None:
    assert format_formation(raw) == expected  # type: ignore[arg-type]
