"""StatsBomb open-data ETL.

Idempotent: every row is upserted on its provider-tagged `source_id` (or, for the stat
tables, on their natural key), so re-running produces no duplicates and refreshes
values that changed.

Verified against the real feed (Copa America 2024, competition 223 / season 282) rather
than from the documentation PDFs. The feed's own `metadata.data_version` is 1.1.0, which
lives on the match records, not on the events:

* Event ids are **UUID strings**; our `id` is a surrogate and `source_id` keeps the UUID.
* Events for a penalty shootout are period 5. They are excluded here (see
  `MAX_PERIOD`) because `matches.home_score`/`away_score` exclude them too.
* A completed pass has **no** `outcome` key at all, so it is stored as "Complete".
* `location`/`player` are absent on some events, so both are nullable.
* `statsbomb_xg` is present on every shot.
* Lineups' `positions[]` spells overlap, can be reversed, and use `to: null` for a
  spell that runs to the final whistle, so minutes are taken over the whole appearance
  window rather than summed per spell (see `parse_lineups`). Minutes follow StatsBomb's
  match clock, which includes stoppage: a full 90-minute match reports ~93-98 minutes
  and the extra-time final reports up to 124.

Run it with `uv run --project backend python scripts/etl_statsbomb.py --help`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.counts import (
    COMPLETED_PASS_OUTCOME,
    aggregate_player,
    aggregate_team,
    format_formation,
)
from app.analytics.types import EventRecord
from app.core.config import Settings, get_settings
from app.core.db import dispose_engine, session_scope
from app.core.eventloop import use_psycopg_compatible_event_loop
from app.core.logging import configure_logging, get_logger
from app.models import Event, Formation, Match, Player, PlayerMatchStats, Team, TeamMatchStats
from app.models.base import SOURCE_PREFIX

logger = get_logger(__name__)

DEFAULT_BASE_URL = "https://raw.githubusercontent.com/hudl/open-data/master/data"
DEFAULT_DATA_ROOT = Path("data/raw/statsbomb")

#: StatsBomb period 5 is a penalty shootout. It is not part of the match as scored:
#: `home_score`/`away_score` exclude shootout penalties, so including these events would
#: inflate goals, shots and xG. Periods 1-2 are normal time, 3-4 extra time.
MAX_PERIOD = 4

#: Rows per INSERT statement. Keeps the parameter count well under PostgreSQL's limit
#: (65535) for the wide event table.
BATCH_SIZE = 500

#: Keys present on every event (or on many events) that are NOT the type-specific
#: payload sub-object.
_EVENT_BASE_KEYS = frozenset(
    {
        "id",
        "index",
        "period",
        "timestamp",
        "minute",
        "second",
        "type",
        "possession",
        "possession_team",
        "play_pattern",
        "team",
        "player",
        "position",
        "location",
        "related_events",
        "duration",
        "under_pressure",
        "off_camera",
        "out",
        "counterpress",
    }
)

#: StatsBomb type names that do not survive a naive slugify.
_TYPE_OVERRIDES = {
    "Ball Receipt*": "ball_receipt",
    "50/50": "fifty_fifty",
}

#: `Duel` is split by its duel type so a tackle is identifiable from `event_type` alone
#: (needed by Phase 2's PPDA) without adding a column to the schema.
_DUEL_TYPE_MAP = {"Tackle": "tackle", "Aerial Lost": "aerial_lost"}


def source_id(kind: str, value: str | int) -> str:
    """Build the provider-tagged identity used for idempotent upserts."""
    return f"{SOURCE_PREFIX}:{kind}:{value}"


def slugify(value: str) -> str:
    """Lowercase, non-alphanumerics to underscores."""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def type_payload(event: dict[str, Any]) -> dict[str, Any] | None:
    """Return the event's type-specific sub-object (``pass``, ``shot``, ``duel``, ...).

    StatsBomb names it after the type (`pass`, `shot`, `50_50`, `ball_receipt`), so
    rather than hard-coding that mapping we take the one extra top-level key holding a
    dict. Verified against every event in a full match: exactly one such key.
    """
    for key, value in event.items():
        if key not in _EVENT_BASE_KEYS and isinstance(value, dict):
            return value
    return None


def normalise_event_type(raw_type: str, event: dict[str, Any]) -> str:
    """Map a StatsBomb type name onto our normalised `event_type` set."""
    if raw_type == "Duel":
        duel_type = (type_payload(event) or {}).get("type") or {}
        return _DUEL_TYPE_MAP.get(str(duel_type.get("name")), "duel")
    if raw_type in _TYPE_OVERRIDES:
        return _TYPE_OVERRIDES[raw_type]
    return slugify(raw_type) or "unknown"


def event_outcome(event: dict[str, Any]) -> str | None:
    """Extract the type-specific outcome name.

    A completed pass carries no `outcome` key at all, so it is recorded as "Complete".
    That keeps `pass_accuracy` from having to treat "missing" and "Incomplete"
    differently, and makes the `Unknown` / `Pass Offside` outcomes visible rather than
    silently counted as completions.
    """
    outcome = (type_payload(event) or {}).get("outcome")
    if isinstance(outcome, dict):
        return str(outcome.get("name")) if outcome.get("name") else None
    if event.get("type", {}).get("name") == "Pass":
        return COMPLETED_PASS_OUTCOME
    return None


def event_xg(event: dict[str, Any]) -> float | None:
    """Shot xG, or None for anything that is not a shot."""
    if event.get("type", {}).get("name") != "Shot":
        return None
    value = (type_payload(event) or {}).get("statsbomb_xg")
    return float(value) if value is not None else None


def _location(event: dict[str, Any]) -> tuple[float | None, float | None]:
    location = event.get("location")
    if not isinstance(location, list) or len(location) < 2:
        return None, None
    return float(location[0]), float(location[1])


def parse_minutes(value: str | None) -> int | None:
    """Parse StatsBomb's ``"MM:SS"`` clock (which can exceed 90) into whole minutes."""
    if not value or ":" not in value:
        return None
    minutes, _, seconds = value.partition(":")
    try:
        return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class ParsedEvent:
    """One event, normalised and ready to load."""

    source_id: str
    minute: int
    second: int
    period: int
    event_type: str
    team_source_id: str
    player_source_id: str | None
    x: float | None
    y: float | None
    outcome: str | None
    xg: float | None
    related_source_id: str | None
    possession_id: int | None
    is_goal_assist: bool
    # For substitution events: the source id of the player coming ON.
    replacement_player_source_id: str | None = None

    def to_row(self) -> dict[str, Any]:
        """The database row (without the surrogate ids, which the DB assigns)."""
        return {
            "source_id": self.source_id,
            "minute": self.minute,
            "second": self.second,
            "event_type": self.event_type,
            "x": self.x,
            "y": self.y,
            "outcome": self.outcome,
            "xg": self.xg,
            "possession_id": self.possession_id,
        }

    def to_record(self, team_id: int, player_id: int | None) -> EventRecord:
        """The analytics input, with surrogate ids resolved."""
        return EventRecord(
            event_type=self.event_type,
            team_id=team_id,
            player_id=player_id,
            x=self.x,
            y=self.y,
            outcome=self.outcome,
            xg=self.xg,
            is_goal_assist=self.is_goal_assist,
            possession_id=self.possession_id,
            minute=self.minute,
            second=self.second,
        )


@dataclass(frozen=True, slots=True)
class PlayerAppearance:
    """A player's involvement in one match, derived from the lineups file."""

    player_source_id: str
    name: str
    team_source_id: str
    team_name: str
    minutes_played: int
    position_played: str | None


def parse_events(raw_events: Iterable[dict[str, Any]]) -> tuple[list[ParsedEvent], int]:
    """Normalise raw events.

    Returns the parsed events and the number skipped because they belong to a penalty
    shootout, so the ETL can report what it dropped.
    """
    parsed: list[ParsedEvent] = []
    skipped_shootout = 0

    for event in raw_events:
        period = int(event.get("period", 1))
        if period > MAX_PERIOD:
            skipped_shootout += 1
            continue

        payload = type_payload(event) or {}
        related = event.get("related_events") or []
        x, y = _location(event)

        raw_type = str(event["type"]["name"])
        event_type = normalise_event_type(raw_type, event)

        # For substitution events, capture the incoming replacement player.
        replacement_player_src: str | None = None
        if event_type == "substitution":
            replacement_raw_id = (
                (event.get("substitution") or {}).get("replacement") or {}
            ).get("id")
            if replacement_raw_id is not None:
                replacement_player_src = source_id("player", int(replacement_raw_id))

        parsed.append(
            ParsedEvent(
                # Verified as a UUID string in the current feed, not an integer.
                source_id=source_id("event", str(event["id"])),
                minute=int(event.get("minute", 0)),
                second=int(event.get("second", 0)),
                period=period,
                event_type=event_type,
                team_source_id=source_id("team", int(event["team"]["id"])),
                player_source_id=(
                    source_id("player", int(event["player"]["id"])) if event.get("player") else None
                ),
                x=x,
                y=y,
                outcome=event_outcome(event),
                xg=event_xg(event),
                related_source_id=(source_id("event", str(related[0])) if related else None),
                possession_id=(
                    int(event["possession"]) if event.get("possession") is not None else None
                ),
                is_goal_assist=bool(payload.get("goal_assist")),
                replacement_player_source_id=replacement_player_src,
            )
        )

    return parsed, skipped_shootout


@dataclass(frozen=True, slots=True)
class _PositionSpell:
    """One raw ``positions[]`` entry.

    The feed's spells for a single player are *not* a clean partition: they overlap
    (a starting slot is repeated alongside the tactical-shift spells), they can be
    reversed (``from`` 116:37 with ``to`` 96:47), and ``to`` is ``null`` for any player
    still on the pitch at the end of their appearance. Summing them double-counts, so
    minutes are derived from the player's whole on-pitch window instead.
    """

    position: str | None
    start: int | None
    end: int | None
    end_reason: str | None

    @property
    def duration(self) -> int:
        """Length of the spell, clamped at zero so reversed spans contribute nothing."""
        if self.start is None or self.end is None:
            return 0
        return max(self.end - self.start, 0)


def _parse_spells(raw_positions: Iterable[dict[str, Any]]) -> list[_PositionSpell]:
    return [
        _PositionSpell(
            position=position.get("position"),
            start=parse_minutes(position.get("from")),
            end=parse_minutes(position.get("to")),
            end_reason=position.get("end_reason"),
        )
        for position in raw_positions
    ]


def _appearance_exit(spells: Sequence[_PositionSpell], match_end_seconds: int) -> int | None:
    """When the player left the pitch.

    A substitution-off spell records the real exit; otherwise a spell ending with
    ``to=null`` means they were still on at the final whistle, which StatsBomb clocks
    as the last event of the last period (stoppage time included).
    """
    substituted_off = [
        spell.end
        for spell in spells
        if (spell.end_reason or "").startswith("Substitution - Off") and spell.end is not None
    ]
    if substituted_off:
        return max(substituted_off)
    if any(spell.end is None for spell in spells):
        return match_end_seconds
    ends = [spell.end for spell in spells if spell.end is not None]
    return max(ends) if ends else None


def substitution_windows(
    raw_events: Iterable[dict[str, Any]],
) -> dict[int, tuple[int | None, int | None]]:
    """Exact ``(entry, exit)`` match-clock seconds per player, from substitution events.

    ``Substitution`` events carry both sides of the swap: ``player`` is the player leaving
    the pitch and ``substitution.replacement`` the one coming on. Substitutes' clock times
    are exact here (e.g. "96:03"), while the lineups file rounds spells to the minute and
    can drop a substitute's entry spell entirely. The exit of a player who is never taken
    off and the entry of a player who starts are left as ``None``; the caller fills them
    from the appearance window.
    """
    windows: dict[int, tuple[int | None, int | None]] = {}
    for raw in raw_events:
        if str(raw.get("type", {}).get("name")) != "Substitution":
            continue
        clock = raw["minute"] * 60 + raw["second"]

        outgoing_id = (raw.get("player") or {}).get("id")
        if outgoing_id is not None:
            entry, _ = windows.get(int(outgoing_id), (None, None))
            windows[int(outgoing_id)] = (entry, clock)

        replacement_id = ((raw.get("substitution") or {}).get("replacement") or {}).get("id")
        if replacement_id is not None:
            _, exit_ = windows.get(int(replacement_id), (None, None))
            windows[int(replacement_id)] = (clock, exit_)

    return windows


def parse_lineups(
    raw_lineups: Iterable[dict[str, Any]],
    match_end_seconds: int,
    sub_windows: dict[int, tuple[int | None, int | None]] | None = None,
) -> list[PlayerAppearance]:
    """Flatten a lineups file into one appearance per squad member per match.

    Players who never took the field have an empty `positions` list; they are kept with
    zero minutes so the squad is complete. ``match_end_seconds`` is the clock of the
    last on-pitch event, used to close spells that run to the final whistle.

    ``sub_windows`` (from `substitution_windows`) holds exact entry/exit clocks taken from
    the match's `Substitution` events. The spells list is the only source of a player's
    positions, but it is not authoritative for time: it rounds to the minute and the feed
    sometimes drops a substitute's entry spell altogether, which would report a goal
    scoring substitute as having played a few minutes. Each source fills the other's gaps
    and the wider window wins; a substitution entry also implies the player was on the
    pitch until either a recorded exit or the final whistle.
    """
    appearances: list[PlayerAppearance] = []

    for team in raw_lineups:
        team_source = source_id("team", int(team["team_id"]))
        for player in team.get("lineup", []):
            spells = _parse_spells(player.get("positions") or [])
            entry = min((spell.start for spell in spells if spell.start is not None), default=None)
            exit_ = _appearance_exit(spells, match_end_seconds) if spells else None

            # Exact times from the substitution events widen (never shrink) the window.
            sub_entry, sub_exit = (sub_windows or {}).get(int(player["player_id"]), (None, None))
            if sub_entry is not None and (entry is None or sub_entry < entry):
                entry = sub_entry
            if sub_exit is not None and exit_ is not None and sub_exit > exit_:
                exit_ = sub_exit
            # Came on per the events but no source recorded an exit: they stayed on.
            if sub_entry is not None and exit_ is None:
                exit_ = match_end_seconds

            # The most representative position is the longest spell; `max` keeps the
            # earliest spell on a tie, which preserves a starter's starting slot.
            position_played: str | None = None
            if spells:
                best = max(
                    spells,
                    key=lambda spell: max(
                        (spell.end if spell.end is not None else (exit_ or spell.start or 0))
                        - (spell.start or 0),
                        0,
                    ),
                )
                position_played = best.position

            minutes = 0
            if entry is not None and exit_ is not None:
                minutes = round(max(exit_ - entry, 0) / 60)

            appearances.append(
                PlayerAppearance(
                    player_source_id=source_id("player", int(player["player_id"])),
                    name=str(player.get("player_name") or player.get("player_nickname") or ""),
                    team_source_id=team_source,
                    team_name=str(team.get("team_name", "")),
                    minutes_played=minutes,
                    position_played=position_played,
                )
            )

    return appearances


def parse_match(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise one matches-file entry."""
    return {
        "source_id": source_id("match", int(raw["match_id"])),
        "competition": str(raw["competition"]["competition_name"]),
        "season": str(raw["season"]["season_name"]),
        "match_date": date.fromisoformat(str(raw["match_date"])),
        "home_score": raw.get("home_score"),
        "away_score": raw.get("away_score"),
        "home_team_source_id": source_id("team", int(raw["home_team"]["home_team_id"])),
        "away_team_source_id": source_id("team", int(raw["away_team"]["away_team_id"])),
        "home_team_name": str(raw["home_team"]["home_team_name"]),
        "away_team_name": str(raw["away_team"]["away_team_name"]),
        "home_team_country": (raw["home_team"].get("country") or {}).get("name"),
        "away_team_country": (raw["away_team"].get("country") or {}).get("name"),
    }


def parse_formations(raw_events: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract formation rows from `Starting XI` and `Tactical Shift` tactics events."""
    rows: list[dict[str, Any]] = []
    for raw in raw_events:
        if int(raw.get("period", 1)) > MAX_PERIOD:
            continue
        if raw.get("type", {}).get("name") not in {"Starting XI", "Tactical Shift"}:
            continue
        tactics = raw.get("tactics") or {}
        rendered = format_formation(tactics.get("formation"))
        if not rendered:
            continue
        rows.append(
            {
                "team_source_id": source_id("team", int(raw["team"]["id"])),
                "formation_string": rendered,
                "period": int(raw.get("period", 1)),
                "start_minute": int(raw.get("minute", 0)),
                "source_event": source_id("event", str(raw["id"])),
            }
        )
    return rows


def chunked(
    rows: Sequence[dict[str, Any]], size: int = BATCH_SIZE
) -> Iterable[Sequence[dict[str, Any]]]:
    """Split rows into insert-sized batches."""
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


# --------------------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------------------


def download(url: str, destination: Path, *, attempts: int = 5, refresh: bool = False) -> None:
    """Fetch `url` into `destination`, skipping work when the file is already cached.

    Retries with backoff: a burst of requests to raw.githubusercontent.com gets
    throttled, and a throttled response must never be mistaken for a missing file.
    """
    if destination.exists() and not refresh:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                temporary.write_bytes(response.read())
            temporary.replace(destination)
            return
        except Exception as error:
            last_error = error
            time.sleep(min(2.0 * (attempt + 1), 10.0))

    raise RuntimeError(f"Failed to download {url} after {attempts} attempts") from last_error


def load_local_json(path: Path, *, offline: bool) -> Any | None:
    """Read a cached JSON file, or None when absent and we may go online."""
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    if offline:
        raise FileNotFoundError(
            f"{path} is missing and --offline was requested. "
            "Run once without --offline to cache it."
        )
    return None


def fetch_json(url: str, path: Path, *, offline: bool, refresh: bool) -> Any:
    """Return parsed JSON from the cache, downloading it first when needed."""
    cached = load_local_json(path, offline=offline)
    if cached is not None:
        return cached
    download(url, path, refresh=refresh)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------


async def upsert_teams(session: AsyncSession, teams: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Upsert teams by source id and return a source id -> surrogate id map."""
    if not teams:
        return {}

    rows = [
        {
            "source_id": src,
            "name": team["name"],
            "country": team.get("country"),
        }
        for src, team in teams.items()
    ]

    for batch in chunked(rows):
        statement = pg_insert(Team).values(list(batch))
        statement = statement.on_conflict_do_update(
            index_elements=[Team.source_id],
            set_={"name": statement.excluded.name, "country": statement.excluded.country},
        )
        await session.execute(statement)

    result = await session.execute(
        select(Team.source_id, Team.id).where(Team.source_id.in_(list(teams.keys())))
    )
    return {row.source_id: row.id for row in result}


async def upsert_players(
    session: AsyncSession, players: dict[str, dict[str, Any]], team_ids: dict[str, int]
) -> dict[str, int]:
    """Upsert players by source id and return a source id -> surrogate id map."""
    if not players:
        return {}

    rows = [
        {
            "source_id": src,
            "name": player["name"],
            "team_id": team_ids.get(player["team_source_id"]),
            "position": player.get("position"),
        }
        for src, player in players.items()
    ]

    for batch in chunked(rows):
        statement = pg_insert(Player).values(list(batch))
        statement = statement.on_conflict_do_update(
            index_elements=[Player.source_id],
            set_={
                "name": statement.excluded.name,
                "team_id": statement.excluded.team_id,
                "position": statement.excluded.position,
            },
        )
        await session.execute(statement)

    result = await session.execute(
        select(Player.source_id, Player.id).where(Player.source_id.in_(list(players.keys())))
    )
    return {row.source_id: row.id for row in result}


async def upsert_match(session: AsyncSession, row: dict[str, Any], team_ids: dict[str, int]) -> int:
    """Upsert one match and return its surrogate id."""
    values = {
        "source_id": row["source_id"],
        "home_team_id": team_ids[row["home_team_source_id"]],
        "away_team_id": team_ids[row["away_team_source_id"]],
        "competition": row["competition"],
        "season": row["season"],
        "match_date": row["match_date"],
        "home_score": row["home_score"],
        "away_score": row["away_score"],
    }

    statement = pg_insert(Match).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[Match.source_id],
        set_={
            "home_team_id": statement.excluded.home_team_id,
            "away_team_id": statement.excluded.away_team_id,
            "competition": statement.excluded.competition,
            "season": statement.excluded.season,
            "match_date": statement.excluded.match_date,
            "home_score": statement.excluded.home_score,
            "away_score": statement.excluded.away_score,
        },
    )

    return int((await session.execute(statement.returning(Match.id))).scalar_one())


async def insert_events(
    session: AsyncSession,
    match_id: int,
    parsed_events: Sequence[ParsedEvent],
    team_ids: dict[str, int],
    player_ids: dict[str, int],
) -> int:
    """Upsert the match's events, then resolve `related_event_id` to our own ids."""
    if not parsed_events:
        return 0

    rows = [
        {
            **event.to_row(),
            "match_id": match_id,
            "team_id": team_ids[event.team_source_id],
            "player_id": (
                player_ids.get(event.player_source_id) if event.player_source_id else None
            ),
            "replacement_player_id": (
                player_ids.get(event.replacement_player_source_id)
                if event.replacement_player_source_id
                else None
            ),
        }
        for event in parsed_events
    ]

    for batch in chunked(rows):
        statement = pg_insert(Event).values(list(batch))
        statement = statement.on_conflict_do_update(
            index_elements=[Event.source_id],
            set_={
                "match_id": statement.excluded.match_id,
                "minute": statement.excluded.minute,
                "second": statement.excluded.second,
                "event_type": statement.excluded.event_type,
                "team_id": statement.excluded.team_id,
                "player_id": statement.excluded.player_id,
                "x": statement.excluded.x,
                "y": statement.excluded.y,
                "outcome": statement.excluded.outcome,
                "xg": statement.excluded.xg,
                "possession_id": statement.excluded.possession_id,
                "replacement_player_id": statement.excluded.replacement_player_id,
            },
        )
        await session.execute(statement)

    # Second pass: `related_events` arrives as source UUIDs, the column holds our ids.
    related = {
        event.source_id: event.related_source_id
        for event in parsed_events
        if event.related_source_id is not None
    }
    if related:
        result = await session.execute(
            select(Event.source_id, Event.id).where(
                Event.match_id == match_id, Event.source_id.in_(related.values())
            )
        )
        id_by_source = {row.source_id: row.id for row in result}
        pairs = [
            {"source_id": src, "related_event_id": id_by_source[target]}
            for src, target in related.items()
            if target in id_by_source
        ]
        if pairs:
            await session.execute(
                text(
                    "UPDATE events SET related_event_id = :related_event_id "
                    "WHERE source_id = :source_id"
                ),
                pairs,
            )

    return len(rows)


async def upsert_team_stats(
    session: AsyncSession, match_id: int, rows: Sequence[dict[str, Any]]
) -> None:
    """Upsert team aggregates on their natural key (match, team)."""
    if not rows:
        return

    for batch in chunked(rows):
        statement = pg_insert(TeamMatchStats).values(
            [{**row, "match_id": match_id} for row in batch]
        )
        statement = statement.on_conflict_do_update(
            index_elements=[TeamMatchStats.match_id, TeamMatchStats.team_id],
            set_={
                "xg": statement.excluded.xg,
                "shots": statement.excluded.shots,
                "shots_on_target": statement.excluded.shots_on_target,
                "passes": statement.excluded.passes,
                "pass_accuracy": statement.excluded.pass_accuracy,
                "formation": statement.excluded.formation,
            },
        )
        await session.execute(statement)


async def upsert_player_stats(
    session: AsyncSession, match_id: int, rows: Sequence[dict[str, Any]]
) -> None:
    """Upsert player aggregates on their natural key (match, player)."""
    if not rows:
        return

    for batch in chunked(rows):
        statement = pg_insert(PlayerMatchStats).values(
            [{**row, "match_id": match_id} for row in batch]
        )
        statement = statement.on_conflict_do_update(
            index_elements=[PlayerMatchStats.match_id, PlayerMatchStats.player_id],
            set_={
                "team_id": statement.excluded.team_id,
                "minutes_played": statement.excluded.minutes_played,
                "goals": statement.excluded.goals,
                "assists": statement.excluded.assists,
                "xg": statement.excluded.xg,
                "passes": statement.excluded.passes,
                "pass_accuracy": statement.excluded.pass_accuracy,
                "shots": statement.excluded.shots,
                "tackles": statement.excluded.tackles,
                "position_played": statement.excluded.position_played,
            },
        )
        await session.execute(statement)


async def replace_formations(
    session: AsyncSession, match_id: int, rows: Sequence[dict[str, Any]], team_ids: dict[str, int]
) -> None:
    """Replace the match's formation rows (they are small and have no natural key)."""
    await session.execute(
        text("DELETE FROM formations WHERE match_id = :match_id"), {"match_id": match_id}
    )
    if not rows:
        return

    await session.execute(
        pg_insert(Formation).values(
            [
                {
                    "match_id": match_id,
                    "team_id": team_ids[row["team_source_id"]],
                    "formation_string": row["formation_string"],
                    "period": row["period"],
                    "start_minute": row["start_minute"],
                }
                for row in rows
            ]
        )
    )


async def load_match(
    session: AsyncSession,
    raw_match: dict[str, Any],
    raw_events: list[dict[str, Any]],
    raw_lineups: list[dict[str, Any]],
) -> dict[str, int]:
    """Load one match and everything belonging to it, in one transaction."""
    match_row = parse_match(raw_match)
    parsed_events, skipped_shootout = parse_events(raw_events)
    # Spells that run to the final whistle are closed at the last on-pitch event, which
    # carries the match clock including stoppage time.
    match_end_seconds = max(
        (event.minute * 60 + event.second for event in parsed_events), default=0
    )
    appearances = parse_lineups(
        raw_lineups,
        match_end_seconds,
        sub_windows=substitution_windows(raw_events),
    )
    formations = parse_formations(raw_events)

    # Teams: from the fixture, the lineups and (defensively) the events.
    names_in_events = {
        source_id("team", int(raw["team"]["id"])): str(raw["team"]["name"]) for raw in raw_events
    }
    teams: dict[str, dict[str, Any]] = {
        match_row["home_team_source_id"]: {
            "name": match_row["home_team_name"],
            "country": match_row["home_team_country"],
        },
        match_row["away_team_source_id"]: {
            "name": match_row["away_team_name"],
            "country": match_row["away_team_country"],
        },
    }
    for appearance in appearances:
        teams.setdefault(appearance.team_source_id, {"name": appearance.team_name, "country": None})
    for event in parsed_events:
        teams.setdefault(
            event.team_source_id,
            {
                "name": names_in_events.get(event.team_source_id, event.team_source_id),
                "country": None,
            },
        )

    team_ids = await upsert_teams(session, teams)

    players = {
        appearance.player_source_id: {
            "name": appearance.name,
            "team_source_id": appearance.team_source_id,
            "position": appearance.position_played,
        }
        for appearance in appearances
    }
    # Defensive: an event can reference a player missing from the lineups.
    for event in parsed_events:
        if event.player_source_id and event.player_source_id not in players:
            players[event.player_source_id] = {
                "name": event.player_source_id,
                "team_source_id": event.team_source_id,
                "position": None,
            }
        # Also ensure replacement players (substitution target) are known.
        if event.replacement_player_source_id and event.replacement_player_source_id not in players:
            players[event.replacement_player_source_id] = {
                "name": event.replacement_player_source_id,
                "team_source_id": event.team_source_id,
                "position": None,
            }

    player_ids = await upsert_players(session, players, team_ids)
    match_id = await upsert_match(session, match_row, team_ids)
    event_count = await insert_events(session, match_id, parsed_events, team_ids, player_ids)

    # Aggregates: one implementation, in app/analytics.
    records = [
        event.to_record(
            team_id=team_ids[event.team_source_id],
            player_id=(player_ids.get(event.player_source_id) if event.player_source_id else None),
        )
        for event in parsed_events
    ]
    formation_by_team = {row["team_source_id"]: row["formation_string"] for row in formations}

    team_rows = []
    for team_source, team_id in team_ids.items():
        if team_source not in {match_row["home_team_source_id"], match_row["away_team_source_id"]}:
            continue
        team_aggregate = aggregate_team(records, team_id)
        team_rows.append(
            {
                "team_id": team_id,
                "xg": team_aggregate.xg,
                "shots": team_aggregate.shots,
                "shots_on_target": team_aggregate.shots_on_target,
                "passes": team_aggregate.passes,
                "pass_accuracy": team_aggregate.pass_accuracy,
                "formation": formation_by_team.get(team_source),
                # possession_pct / ppda / field_tilt stay NULL until Phase 2.
            }
        )
    await upsert_team_stats(session, match_id, team_rows)

    player_rows = []
    for appearance in appearances:
        player_id = player_ids.get(appearance.player_source_id)
        if player_id is None:
            continue
        player_aggregate = aggregate_player(records, player_id)
        player_rows.append(
            {
                "player_id": player_id,
                "team_id": team_ids[appearance.team_source_id],
                "minutes_played": appearance.minutes_played,
                "goals": player_aggregate.goals,
                "assists": player_aggregate.assists,
                "xg": player_aggregate.xg,
                "passes": player_aggregate.passes,
                "pass_accuracy": player_aggregate.pass_accuracy,
                "shots": player_aggregate.shots,
                "tackles": player_aggregate.tackles,
                "position_played": appearance.position_played,
                # xa stays NULL: the source has no expected assists.
            }
        )
    await upsert_player_stats(session, match_id, player_rows)

    await replace_formations(session, match_id, formations, team_ids)

    return {
        "events": event_count,
        "events_skipped_shootout": skipped_shootout,
        "player_stats": len(player_rows),
        "team_stats": len(team_rows),
        "formations": len(formations),
    }


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------


async def run_etl(
    settings: Settings,
    *,
    competition_id: int,
    season_id: int,
    data_root: Path,
    base_url: str = DEFAULT_BASE_URL,
    offline: bool = False,
    refresh: bool = False,
    match_ids: Sequence[int] | None = None,
) -> dict[str, int]:
    """Load one competition-season (or a subset of its matches)."""
    matches_path = data_root / "matches" / str(competition_id) / f"{season_id}.json"
    raw_matches = fetch_json(
        f"{base_url}/matches/{competition_id}/{season_id}.json",
        matches_path,
        offline=offline,
        refresh=refresh,
    )

    if match_ids:
        wanted = set(match_ids)
        raw_matches = [m for m in raw_matches if int(m["match_id"]) in wanted]
        if not raw_matches:
            raise RuntimeError(f"None of the requested matches exist in {matches_path}")

    totals = {
        "matches": len(raw_matches),
        "events": 0,
        "events_skipped_shootout": 0,
        "player_stats": 0,
        "team_stats": 0,
        "formations": 0,
    }

    logger.info(
        "etl_started competition_id=%s season_id=%s matches=%d data_root=%s",
        competition_id,
        season_id,
        len(raw_matches),
        data_root,
    )

    async with session_scope(settings) as session:
        for raw_match in raw_matches:
            match_id = int(raw_match["match_id"])
            raw_events = fetch_json(
                f"{base_url}/events/{match_id}.json",
                data_root / "events" / f"{match_id}.json",
                offline=offline,
                refresh=refresh,
            )
            raw_lineups = fetch_json(
                f"{base_url}/lineups/{match_id}.json",
                data_root / "lineups" / f"{match_id}.json",
                offline=offline,
                refresh=refresh,
            )

            counts = await load_match(session, raw_match, raw_events, raw_lineups)
            await session.commit()

            for key, value in counts.items():
                totals[key] += value

            logger.info(
                "match_loaded match_id=%s source_events=%d loaded_events=%d "
                "skipped_shootout=%d players=%d",
                match_id,
                len(raw_events),
                counts["events"],
                counts["events_skipped_shootout"],
                counts["player_stats"],
            )

    logger.info(
        "etl_finished matches=%d events=%d skipped_shootout=%d player_stats=%d formations=%d",
        totals["matches"],
        totals["events"],
        totals["events_skipped_shootout"],
        totals["player_stats"],
        totals["formations"],
    )
    return totals


def build_parser() -> argparse.ArgumentParser:
    """CLI definition (also used by the thin wrapper in `scripts/`)."""
    parser = argparse.ArgumentParser(
        description="Load StatsBomb open data into Postgres (idempotent)."
    )
    parser.add_argument("--competition-id", type=int, default=223, help="StatsBomb competition id")
    parser.add_argument("--season-id", type=int, default=282, help="StatsBomb season id")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Where raw JSON is cached and read from",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Raw file base URL")
    parser.add_argument(
        "--offline", action="store_true", help="Fail instead of downloading a missing file"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Re-download files even if they are cached"
    )
    parser.add_argument(
        "--match-id",
        type=int,
        action="append",
        dest="match_ids",
        help="Only load this match id (repeatable)",
    )
    return parser


async def _run_and_dispose(args: argparse.Namespace, settings: Settings) -> dict[str, int]:
    """Run the ETL and always release the engine, inside one event loop."""
    try:
        return await run_etl(
            settings,
            competition_id=args.competition_id,
            season_id=args.season_id,
            data_root=args.data_root,
            base_url=args.base_url,
            offline=args.offline,
            refresh=args.refresh,
            match_ids=args.match_ids,
        )
    finally:
        await dispose_engine()


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings)
    # Before asyncio.run below: psycopg's async driver needs a selector loop on Windows.
    use_psycopg_compatible_event_loop()

    try:
        totals = asyncio.run(_run_and_dispose(args, settings))
    except Exception:
        logger.exception("etl_failed")
        return 1

    print(  # noqa: T201 - the CLI's user-facing summary belongs on stdout
        f"Loaded {totals['matches']} matches, {totals['events']} events "
        f"({totals['events_skipped_shootout']} shootout events skipped), "
        f"{totals['player_stats']} player stat rows, {totals['formations']} formation rows."
    )
    return 0
