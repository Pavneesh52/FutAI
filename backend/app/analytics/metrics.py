"""Advanced analytics metrics (Phase 2).

Pure functions: no database, no network, no LLM. Every function takes a sequence of
``EventRecord`` and returns a typed result.

Metric definitions are documented in ``docs/metrics.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.analytics.counts import COMPLETED_PASS_OUTCOME
from app.analytics.types import EventRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Event types that count as defensive actions for PPDA.
#: Tackles (from Duel split), Interceptions, Fouls Committed.
#: Aerial Lost duels are excluded — the conventional PPDA definition counts only
#: ground-level pressing actions.
PPDA_DEFENSIVE_TYPES = frozenset({"tackle", "interception", "foul_committed"})

#: The boundary of a team's own 60% of the pitch (from their perspective).
#: Opponent passes here are the PPDA numerator. On a 120-unit pitch, 60% = 72.
PPDA_OWN_60_X = 72.0

#: The boundary of a team's attacking 40% (= opponent's defensive 40%).
#: The team's defensive actions here are the PPDA denominator.
PPDA_ATTACKING_40_X = 48.0

#: Final third boundary (from acting team's perspective). x ≥ 80 = attacking final third.
FINAL_THIRD_X = 80.0

PASS = "pass"


def possession_pct(events: Sequence[EventRecord], team_id: int) -> float | None:
    """Team's share of total passes, as a percentage.

    Returns ``None`` when the match has zero passes (avoids reporting 0% as a measured
    value for an empty dataset).

    Rationale: StatsBomb provides ``possession`` sequence ids but not explicit duration
    timestamps, so time-based possession is not computable from the open data. Pass-count
    share is the standard proxy (documented in ``docs/metrics.md``).
    """
    total = 0
    team_passes = 0
    for event in events:
        if event.event_type == PASS:
            total += 1
            if event.team_id == team_id:
                team_passes += 1
    if total == 0:
        return None
    return 100.0 * team_passes / total


def ppda(
    events: Sequence[EventRecord],
    team_id: int,
    *,
    all_team_ids: Sequence[int] | None = None,
) -> float | None:
    """Passes Per Defensive Action — a pressing intensity metric.

    PPDA = (opponent passes in the opponent's own 60% of the pitch)
         ÷ (team's defensive actions in the team's attacking 60%)

    Coordinates are from the acting team's perspective on a 120x80 pitch:
    * Opponent's own 60% → opponent events where ``x <= 72``
    * Team's attacking 60% → team events where ``x >= 48``

    A lower PPDA means higher pressing intensity.

    Returns ``None`` when the team has zero qualifying defensive actions, so a
    division-by-zero never occurs and the metric is clearly marked as unmeasurable.
    """
    # Identify the opponent team(s).
    if all_team_ids is not None:
        opp_ids = frozenset(all_team_ids) - {team_id}
    else:
        opp_ids = frozenset(e.team_id for e in events) - {team_id}

    opp_passes_own_60 = 0
    team_def_actions_atk_60 = 0

    for event in events:
        # Opponent passes in their own defensive 60%.
        if (
            event.team_id in opp_ids
            and event.event_type == PASS
            and event.x is not None
            and event.x <= PPDA_OWN_60_X
        ):
            opp_passes_own_60 += 1

        # Team's defensive actions in the team's attacking 40%.
        if (
            event.team_id == team_id
            and event.event_type in PPDA_DEFENSIVE_TYPES
            and event.x is not None
            and event.x >= PPDA_ATTACKING_40_X
        ):
            team_def_actions_atk_60 += 1

    if team_def_actions_atk_60 == 0:
        return None
    return opp_passes_own_60 / team_def_actions_atk_60


def field_tilt(events: Sequence[EventRecord], team_id: int) -> float | None:
    """Proportion of final-third passes belonging to the team.

    field_tilt(team) = team's passes with x ≥ 80
                     ÷ (all teams' passes with x ≥ 80)

    Returns ``None`` when no team has any final-third passes. The property
    ``field_tilt(A) + field_tilt(B) ≈ 1.0`` holds for any two-team match.

    Events with missing coordinates are silently excluded.
    """
    team_ft = 0
    total_ft = 0

    for event in events:
        if event.event_type == PASS and event.x is not None and event.x >= FINAL_THIRD_X:
            total_ft += 1
            if event.team_id == team_id:
                team_ft += 1

    if total_ft == 0:
        return None
    return team_ft / total_ft


def pass_accuracy(events: Sequence[EventRecord], team_id: int) -> float | None:
    """Completed passes as a percentage of attempted passes for a team.

    Returns ``None`` when the team has zero passes.
    """
    total = 0
    completed = 0
    for event in events:
        if event.event_type == PASS and event.team_id == team_id:
            total += 1
            if event.outcome == COMPLETED_PASS_OUTCOME:
                completed += 1
    if total == 0:
        return None
    return 100.0 * completed / total
