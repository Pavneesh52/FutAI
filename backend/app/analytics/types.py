"""Typed inputs for the analytics functions.

This is deliberately a small, dependency-free record rather than the section 6.1
`MatchEvent` pydantic model: analytics must stay importable and testable without the
API schemas (rule R8). Phase 2 extends this with whatever the new metrics need.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventRecord:
    """The subset of an event the analytics functions need.

    ``event_type`` is the normalised type produced by the ETL (see
    ``app.etl.statsbomb.normalise_event_type``), so "Duel" arrives here already split
    into "tackle" / "aerial_lost" / "duel".
    """

    event_type: str
    team_id: int
    player_id: int | None = None
    x: float | None = None
    y: float | None = None
    outcome: str | None = None
    xg: float | None = None
    #: StatsBomb's `pass.goal_assist`. Not persisted on its own: it is folded into the
    #: assist count here so the metric has exactly one implementation.
    is_goal_assist: bool = False
    #: StatsBomb's `possession` sequence id. Used by Phase 2's `possession_sequences`.
    possession_id: int | None = None
    #: Match clock. Phase 2 needs these for possession-sequence duration.
    minute: int = 0
    second: int = 0
