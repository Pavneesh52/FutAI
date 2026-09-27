# Data source

Everything the app knows about football comes from the StatsBomb open-data repository.

- Repository: <https://github.com/hudl/open-data> (the feed that used to live at
  `statsbomb/open-data`; StatsBomb was acquired by Hudl and the old URL still redirects)
- Raw endpoint base used by the ETL:
  `https://raw.githubusercontent.com/hudl/open-data/master/data`
- Licence/attribution: the open data is free to use, but the repository asks that any
  published analysis **states the data source as StatsBomb and displays the StatsBomb
  logo** (available in their Media Pack). Any demo or screenshot of this app is covered
  by that requirement.

## The dataset: Copa América 2024, all 32 matches

| Field | Value |
|---|---|
| Competition id | `223` (Copa America) |
| Season id | `282` (2024) |
| Matches | **32** |
| Teams | 16 |
| Dates | 2024-06-21 → 2024-07-15 (match weeks 1-6) |
| Stages | Group Stage, Quarter-finals, Semi-finals, 3rd Place Final, Final |
| `metadata.data_version` | `1.1.0` |
| Raw events on disk | ~87 MB (all 32 matches) |

### Why this one

The plan asks for a competition-season of roughly 20-30 matches with lineups **and**
events. Measured across every small candidate in the repository, no competition-season
lands in that window: the options are a complete tournament of 31-32 matches or a
partial league. Counts below are from the repository's own season files.

| Competition-season | Matches | Teams | Note |
|---|---|---|---|
| **Copa América 2024** (223/282) | **32** | 16 | Complete tournament; lineups + events for all 32 |
| UEFA Women's Euro 2022 (53/106) | 31 | 16 | Complete; smallest, ships 360 data |
| UEFA Women's Euro 2025 (53/315) | 31 | 16 | Complete; ships 360 data |
| La Liga 2020/2021 (11/90) | 35 | 19 | Partial season: no team has full coverage |
| UEFA Euro 2024 (55/282) | 51 | 24 | Too large |
| Women's World Cup 2019 (72/30) | 52 | 24 | Too large |
| Copa del Rey 1983/84, NASL 1977, U20 WC 1979, Liga Profesional 1981 | 1 each | 2 | Final-only releases |

Copa América 2024 was chosen because it is the smallest **complete** competition-season
with lineups and events for every match, so each team's full run through the tournament
is present - the strongest reading of "full-season coverage". It overshoots the stated
20-30 by two matches; loading only the 24 group-stage matches would fit the letter of
the range but drop the final and every knockout match.

The teams are also recognisable (Argentina, Brazil, Colombia, Messi, the final won 1-0
after extra time), which matters for the Phase 4 gate where a non-technical person has
to ask the app questions and judge the answers.

## Files the ETL reads

| Path | Contents |
|---|---|
| `competitions.json` | One row per competition-season (not currently ingested) |
| `matches/{competition_id}/{season_id}.json` | The 32 match records |
| `events/{match_id}.json` | Every event of one match (2-3 MB each) |
| `lineups/{match_id}.json` | Both squads, with position spells |
| `three-sixty/{match_id}.json` | 360 freeze-frames - **not used** by this project |

Responses are cached under `data/raw/statsbomb/` (gitignored), so re-running the ETL is
offline and fast.

## Verified schema facts (read from the JSON, not the PDFs)

The repository documents its formats only in PDFs, which are easy to misread and drift
from the data. Everything below was checked against the real files, and each fact is
what the ETL or a test depends on.

### Matches

- `home_score` / `away_score` are **top-level**, not inside the team objects.
- Team objects are nested: `home_team.home_team_id`, `home_team.home_team_name`,
  `home_team.country.name`.
- `competition_stage` (id + name) and `match_week` exist but are only used for ordering.
- `metadata.data_version` is `1.1.0`; the **data version lives here**, not on events.

### Events

- Event ids are **UUID strings** in the current feed, not integers.
- `possession` (the possession sequence id) is present on **every** event.
- `location` and `player` are **absent on some events** (Half Start/End and friends), so
  both are nullable. In the final, 44 events have no coordinates.
- `statsbomb_xg` is present on **every** shot (30/30 in the final).
- Exactly one extra top-level key holds the type-specific payload (`pass`, `shot`,
  `duel`, `50_50`, `ball_receipt`, ...), so the ETL finds it structurally rather than
  from a hard-coded map.
- A **completed pass carries no `outcome` key at all**; only failed passes have one.
  The ETL stores a completed pass as `outcome = "Complete"`. Note that `Unknown` and
  `Pass Offside` are real pass outcomes, so pass accuracy is *not* simply
  "every pass that has an outcome is incomplete" - Phase 2 defines that rule explicitly.
- **Period 5 is a penalty shootout.** `home_score`/`away_score` exclude shootout
  penalties, so counting them inflates goals, shots and xG: the quarter-final is a 1-1
  match containing 6 shootout goals. The ETL loads periods 1-4 only and reports how many
  events it skipped.
- **An own goal is not a shot.** StatsBomb emits it as a pair of events at the same
  minute: `Own Goal Against` (the scorer's own team, carrying the player) and
  `Own Goal For` (the team credited with the goal, with no player). Ecuador 3-1 Jamaica
  (match 3939980) is the season's only one, and its scoreline reconciles only if the
  `Own Goal For` event is counted. The consequence for the metrics:
  - a team's goals = its `shot` events with outcome `Goal` **plus** its `own_goal_for`
    events, so a side's tally can exceed its shot total;
  - a player's goals count only shots they took, so the defender who scores an
    `own_goal_against` is not credited with a goal.
  - `team_match_stats` stores no goals column at all (the scoreline is on `matches`),
    so Phase 2 must apply this rule wherever it reports goals.
- `minute` is the match clock, and it is **not monotonic across periods**: period 1 ends
  at 47:47 and period 2 restarts at 45:00. Stoppage time is included in the clock.
- `tactics.formation` is a single **integer** (`442`), not a list of positions, and it
  appears on `Starting XI` as well as `Tactical Shift`.

### Lineups

- `positions[]` is a list of *position spells*, and it is **not a clean partition** of a
  player's time on the pitch:
  - spells **overlap** - a starting slot is repeated alongside the tactical-shift spells,
    so summing them double-counts minutes;
  - a spell can be **reversed** (`from` 116:37 with `to` 96:47);
  - `to` is **`null`** for a spell that runs to the final whistle, and that same player
    may also carry a substituted-off spell at an earlier minute.
- Because of the above, `minutes_played` is taken over the player's **whole appearance
  window** - entry = earliest spell start, exit = the substituted-off time if present,
  otherwise the match's final whistle - and `position_played` is the **longest spell**
  (ties go to the earliest, preserving a starter's starting slot).

  Worked examples from the 2024 final (`match_id` 3943077), where the match clock ends
  at **124:28**:

  | Player | Spells | Minutes | Position |
  |---|---|---|---|
  | Ángel Di María | `00:00→116:15` (subbed off), `16:08→66:26`, `66:26→null` | **116** | Right Midfield |
  | Giovani Lo Celso | `116:37→96:47` (reversed), `96:47→96:47`, `96:47→null` | **28** | Center Defensive Midfield |
  | Nicolás Otamendi | `116:15→116:37`, `116:37→null` | **8** | Center Back |
  | Unused substitute | *(no spells)* | **0** | `NULL` |

- **Minutes include stoppage time** and follow StatsBomb's match clock, so a full
  90-minute match reports ~93-98 minutes and a player who saw out the extra-time final
  reports 124. This is a deliberate convention; it is not the same as the 90/120 a
  broadcast graphic would show.

## Event-type mapping

`event_type` is a normalised slug of the StatsBomb type name, with three deliberate
special cases (see `normalise_event_type` in `app/etl/statsbomb.py`):

| StatsBomb type | `event_type` |
|---|---|
| `Ball Receipt*` | `ball_receipt` |
| `50/50` | `fifty_fifty` |
| `Duel`, `duel.type = Tackle` | `tackle` |
| `Duel`, `duel.type = Aerial Lost` | `aerial_lost` |
| `Duel`, any other duel type | `duel` |
| anything else | slugified name (`Pass` → `pass`, `Carry` → `carry`) |

`Duel` is split by duel type so a tackle is identifiable from `event_type` alone, which
Phase 2 needs for PPDA, without adding a column to the schema.

## Season totals (all 32 matches, from the cached feed)

Checked by re-parsing every match: 100,324 events, of which 100,229 are in periods 1-4
and 95 are shootout events that the ETL drops. 751 shots, 69 goal shots, 1 own goal, 188
formation rows and 1,618 player-match appearances. One match went to extra time (the
final) and four went to a shootout. Every event carries `possession`; `location` is
missing from 1,145 and `player` from 608.

## Reproducing the load

```bash
docker compose up -d
uv run --project backend python scripts/seed.py   # alembic upgrade head + ETL, idempotent
```

To reload from the network instead of the cache, add `--refresh`; to load a subset,
`--match-ids 3943077`.
