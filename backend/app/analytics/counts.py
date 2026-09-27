"""Count aggregations over events.

Phase 1 uses these to populate ``team_match_stats`` and ``player_match_stats``. They live
here rather than in the ETL script so that every metric has exactly one implementation
(Phase 2 adds PPDA, field tilt and possession alongside them and documents the wording in
``docs/metrics.md``).

Pure functions: no database, no network, no LLM.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.analytics.types import EventRecord

#: The ETL stores a successful pass with this outcome, because StatsBomb omits the
#: `outcome` key entirely when a pass is completed (verified against real event JSON).
COMPLETED_PASS_OUTCOME = "Complete"

#: Shot outcomes that count as on target, matching the Phase 2 definition in
#: IMPLEMENTATION.md ("goal/saved/saved-to-post"). Hitting the woodwork ("Post") is
#: deliberately excluded. Phase 2 owns the final wording in docs/metrics.md.
ON_TARGET_OUTCOMES = frozenset({"Goal", "Saved", "Saved to Post"})

GOAL_OUTCOME = "Goal"

PASS = "pass"
SHOT = "shot"
TACKLE = "tackle"


@dataclass(frozen=True, slots=True)
class TeamAggregate:
    """Simple team totals for one match."""

    shots: int
    shots_on_target: int
    passes: int
    completed_passes: int
    xg: float

    @property
    def pass_accuracy(self) -> float | None:
        """Completed passes as a percentage of attempted passes.

        ``None`` when the team attempted no passes, so an empty match never reports 0%
        accuracy as if it were measured.
        """
        if self.passes == 0:
            return None
        return 100.0 * self.completed_passes / self.passes


@dataclass(frozen=True, slots=True)
class PlayerAggregate:
    """Simple player totals for one match."""

    goals: int
    assists: int
    shots: int
    xg: float
    passes: int
    completed_passes: int
    tackles: int

    @property
    def pass_accuracy(self) -> float | None:
        """See `TeamAggregate.pass_accuracy`."""
        if self.passes == 0:
            return None
        return 100.0 * self.completed_passes / self.passes


def aggregate_team(events: Iterable[EventRecord], team_id: int) -> TeamAggregate:
    """Total shots, on-target shots, passes, completed passes and xG for one team."""
    shots = shots_on_target = passes = completed_passes = 0
    xg = 0.0

    for event in events:
        if event.team_id != team_id:
            continue
        if event.event_type == SHOT:
            shots += 1
            xg += event.xg if event.xg is not None else 0.0
            if event.outcome in ON_TARGET_OUTCOMES:
                shots_on_target += 1
        elif event.event_type == PASS:
            passes += 1
            if event.outcome == COMPLETED_PASS_OUTCOME:
                completed_passes += 1

    return TeamAggregate(
        shots=shots,
        shots_on_target=shots_on_target,
        passes=passes,
        completed_passes=completed_passes,
        xg=xg,
    )


def aggregate_player(events: Iterable[EventRecord], player_id: int) -> PlayerAggregate:
    """Goals, assists, shots, xG, passes and tackles for one player.

    Goals come only from shots this player took. Own goals are attributed to the
    opponent (the scorer's `own_goal_for` event is on the other team), which is the
    conventional treatment and keeps a player's goal tally honest.
    """
    goals = assists = shots = passes = completed_passes = tackles = 0
    xg = 0.0

    for event in events:
        if event.player_id == player_id:
            if event.event_type == SHOT:
                shots += 1
                xg += event.xg if event.xg is not None else 0.0
                if event.outcome == GOAL_OUTCOME:
                    goals += 1
            elif event.event_type == PASS:
                passes += 1
                if event.outcome == COMPLETED_PASS_OUTCOME:
                    completed_passes += 1
                if event.is_goal_assist:
                    assists += 1
            elif event.event_type == TACKLE:
                tackles += 1

    return PlayerAggregate(
        goals=goals,
        assists=assists,
        shots=shots,
        xg=xg,
        passes=passes,
        completed_passes=completed_passes,
        tackles=tackles,
    )


def format_formation(formation: int | str | None) -> str | None:
    """Render StatsBomb's integer formation as the conventional string.

    ``442 -> "4-4-2"``, ``41212 -> "4-1-2-1-2"``. Values that are already non-numeric
    are passed through, so a future source that sends "4-4-2" is not mangled.
    """
    if formation is None:
        return None
    text = str(formation).strip()
    if not text:
        return None
    if not text.isdigit():
        return text
    return "-".join(text)
