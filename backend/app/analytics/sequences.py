"""Possession-sequence analysis (Phase 2).

Groups consecutive events by StatsBomb's ``possession`` id into chains and summarises
each chain. Pure function: no database, no network, no LLM.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.analytics.types import EventRecord

PASS = "pass"
SHOT = "shot"

#: Zone boundaries on the 120-unit pitch (from the acting team's perspective).
DEFENSIVE_THIRD_X = 40.0
ATTACKING_THIRD_X = 80.0


def _zone_name(x: float) -> str:
    """Classify an x-coordinate into a pitch zone."""
    if x < DEFENSIVE_THIRD_X:
        return "defensive_third"
    if x < ATTACKING_THIRD_X:
        return "middle_third"
    return "attacking_third"


@dataclass(frozen=True, slots=True)
class PossessionSequence:
    """One uninterrupted possession chain."""

    possession_id: int
    team_id: int
    start_zone: str | None  # None when no event has coordinates
    end_zone: str | None
    duration_seconds: int  # clock-based, so stoppage time is included
    pass_count: int
    ended_in_shot: bool


def possession_sequences(events: Sequence[EventRecord]) -> list[PossessionSequence]:
    """Group events by ``possession_id`` and summarise each chain.

    Events without a ``possession_id`` are silently skipped.

    The team that owns each possession is the team of the *first* event in the chain
    (StatsBomb attributes every event in a possession to the possessing team, except
    for defensive actions by the opponent, but the first event is always the team that
    initiates the sequence).

    Duration is computed from the match clock (``minute:second``) of the first and last
    event. This includes stoppage time (a StatsBomb convention). If a possession has
    only one event, duration is 0.
    """
    # Gather events by possession_id, preserving insertion order.
    by_poss: dict[int, list[EventRecord]] = defaultdict(list)
    for event in events:
        if event.possession_id is not None:
            by_poss[event.possession_id].append(event)

    results: list[PossessionSequence] = []
    for poss_id in sorted(by_poss):
        chain = by_poss[poss_id]
        if not chain:
            continue

        team_id = chain[0].team_id

        # Zones from coordinates.
        coords_with_x = [e for e in chain if e.x is not None]
        start_zone = _zone_name(coords_with_x[0].x) if coords_with_x else None  # type: ignore[arg-type]
        end_zone = _zone_name(coords_with_x[-1].x) if coords_with_x else None  # type: ignore[arg-type]

        # Duration from match clock.
        first = chain[0]
        last = chain[-1]
        duration = (last.minute * 60 + last.second) - (first.minute * 60 + first.second)
        if duration < 0:
            duration = 0  # Defensive: clock resets across periods.

        pass_count = sum(1 for e in chain if e.event_type == PASS)
        ended_in_shot = any(e.event_type == SHOT for e in chain)

        results.append(
            PossessionSequence(
                possession_id=poss_id,
                team_id=team_id,
                start_zone=start_zone,
                end_zone=end_zone,
                duration_seconds=duration,
                pass_count=pass_count,
                ended_in_shot=ended_in_shot,
            )
        )

    return results
