# IMPLEMENTATION.md — AI Football Match Analyst

> A phase-by-phase build guide designed to be executed **with an AI coding assistant** (Claude Code, Cursor, Copilot, etc.).
> Build the MVP first (Phases 0–4). Every later phase adds a feature on top of a working system.

---

## 0. How to use this file

### The workflow (repeat for every phase)

1. Open a **fresh AI session** for the phase (keeps context clean).
2. Give the AI these three things, in this order:
   - Sections **1–4** of this file (rules, stack, structure, conventions) — always.
   - Section **6** (shared contracts) — always.
   - The **one phase section** you are implementing.
3. Paste the phase's **"AI prompt"** block.
4. Let the AI implement. Run the phase's **acceptance checks** yourself. Do not trust "it works" without running them.
5. Commit with the phase's commit message, tick the box in the **Progress Tracker** (section 5), and write 3–5 lines in the phase's **Handoff notes** (what was built, deviations, known issues). The next session starts by reading those notes.
6. Only then start the next phase.

### Rules for working with the AI
- **One phase per session. Never skip ahead.** If the AI proposes adding "just a bit of Phase 6" during Phase 3, say no.
- **Tests first or alongside**, never "later". A phase is not done until its tests pass.
- **Ask the AI to plan before coding**: "List the files you will create/change and why, then wait for my OK." Approve, then let it code.
- **Verify library APIs against current docs** (FastAPI, SQLAlchemy 2.x, LangGraph, Grok / xAI SDK, Qdrant client change often). Tell the AI: "Check the current official docs; do not rely on memory for API signatures."
- **If a phase's acceptance checks fail after 2 fix attempts**, stop, paste the failing output into a new session with the phase section, and ask for root-cause analysis before more edits.
- **Keep scope tight.** Anything not listed under a phase's "Scope" goes into `BACKLOG.md`, not into the code.

---

## 1. Project brief and non-negotiable rules

**Product:** A web app where a user picks a football match, sees its stats, and asks questions in natural language. A multi-agent system answers with a grounded analysis: every number traces to a deterministic tool call, and tactical claims cite sources.

**Non-negotiable rules (enforce in every phase):**

| # | Rule |
|---|------|
| R1 | **The LLM never generates statistics.** Every number in any output comes from a tool result. |
| R2 | **The LLM never writes SQL** or free-form queries. It only calls typed tools. |
| R3 | **Every agent/tool boundary is validated by Pydantic.** Malformed output fails fast. |
| R4 | **Every external call has a timeout** (LLM, DB, Qdrant, HTTP). |
| R5 | **Failures degrade, they don't crash.** Tool/LLM failure returns a clear degraded response. |
| R6 | **Facts and interpretation are separated** in reports ("What happened" vs "Analysis"). |
| R7 | **No secrets in the repo.** `.env` only; `.env.example` documents keys. |
| R8 | **Tools are unit-testable with no LLM.** |
| R9 | **State stays small:** store references to evidence (e.g. `event:431`), not raw payloads. |
| R10 | **Data source is swappable** behind `MatchDataService`. |

---

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + Vite + TypeScript + Tailwind + Recharts | React Query for server state |
| Backend | Python 3.11+, FastAPI, Pydantic v2 | async where I/O-bound |
| ORM/migrations | SQLAlchemy 2.x + Alembic | |
| DB | PostgreSQL 16 | via docker-compose |
| Vector DB | Qdrant | via docker-compose (Phase 7+) |
| LLM | Llama 3.3 70B (Groq / OpenAI-compatible) | model name from env `LLM_MODEL`; key from `GROQ_API_KEY` |
| Orchestration | LangGraph | Phase 5+ |
| Observability | LangSmith | Phase 11 |
| Testing | pytest, pytest-asyncio, httpx; Vitest + Testing Library (FE) | |
| Lint/format | ruff + mypy (BE); eslint + prettier (FE) | |
| Data | StatsBomb open data (JSON on GitHub) | Check and follow its attribution/licence terms. Pitch is 120×80; coordinates are from the acting team's perspective. |

---

## 3. Repo structure

```
football-ai-analyst/
├── frontend/
│   └── src/{components,pages,hooks,api,types}/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── agents/         # one file per agent (prompt + logic)
│   │   ├── graph/          # LangGraph: state, nodes, edges, builder
│   │   ├── tools/          # deterministic tool functions
│   │   ├── analytics/      # pure metric functions (PPDA, field tilt, ...)
│   │   ├── rag/            # ingestion, chunking, retrieval, qdrant client
│   │   ├── models/         # SQLAlchemy ORM
│   │   ├── schemas/        # Pydantic request/response/state
│   │   ├── services/       # MatchDataService, business logic
│   │   └── core/           # config, logging, db session, errors, security
│   ├── alembic/
│   ├── tests/{unit,agents,graph,rag,api,eval}/
│   ├── pyproject.toml
│   └── Dockerfile
├── data/                   # raw/staged datasets (gitignored except samples)
├── knowledge_base/         # tactical docs for RAG (markdown)
├── scripts/                # ETL, ingestion, seed, eval runner
├── docs/                   # metric definitions, decisions (ADRs)
├── docker-compose.yml
├── .env.example
├── BACKLOG.md
├── IMPLEMENTATION.md
└── README.md
```

---

## 4. Conventions

- **Python:** type hints everywhere; `ruff` + `mypy --strict` on `app/`; functions small and single-purpose; no business logic in routers.
- **Errors:** custom hierarchy in `app/core/errors.py`: `AppError` → `MatchNotFoundError`, `PlayerNotFoundError`, `DataUnavailableError`, `ToolExecutionError`, `LLMError`, `LLMTimeoutError`, `ValidationFailedError`. Routers map them to HTTP codes (404/422/502/504).
- **Config:** `pydantic-settings` reading `.env`; one `Settings` object in `app/core/config.py`.
- **Logging:** structured JSON logs with `request_id` and (later) `agent_run_id`.
- **Tests:** `tests/unit` needs no network and no LLM. LLM tests go in `tests/agents` and are marked `@pytest.mark.llm` (skipped by default; run with `-m llm`).
- **Commits:** Conventional Commits, one commit per phase minimum (`feat(phase-3): single agent with tools`).
- **API contract:** every response is a Pydantic model; generate TS types for the frontend from OpenAPI (e.g. `openapi-typescript`).
- **Definition of Done (all phases):** code merged, tests pass, `ruff`/`mypy` clean, README/docs updated, acceptance checks run, tracker ticked, handoff notes written.

---

## 5. Progress tracker

```
RELEASE 1 — MVP
[x] Phase 0  Foundation
[x] Phase 1  Data pipeline + database
[x] Phase 2  Analytics library
[x] Phase 3  Single agent with tools  (+ golden eval set v1)
[x] Phase 4  Thin UI                  ← MVP GATE

RELEASE 2 — AGENTIC CORE
[ ] Phase 5  LangGraph skeleton
[ ] Phase 6  Multi-agent analysis

RELEASE 3 — KNOWLEDGE + TRUST
[ ] Phase 7  RAG
[ ] Phase 8  Critic + refinement loop

RELEASE 4 — FULL PRODUCT
[ ] Phase 9  Frontend v2 (streaming, timeline, tactical, comparison)

RELEASE 5 — PRODUCTION
[ ] Phase 10 Full evaluation
[ ] Phase 11 Observability
[ ] Phase 12 Security + deployment

RELEASE 6 — STRETCH
[ ] Phase 13 Backlog items
```

---

## 6. Shared contracts

These are the interfaces the phases build against. Create them in the phase where they first appear; do not change them silently later (update this section and the Handoff notes if you must).

### 6.1 Tool output schemas (`app/schemas/tools.py`) — Phase 2/3

```python
from pydantic import BaseModel, Field
from typing import Optional

class TeamMatchStats(BaseModel):
    match_id: int
    team_id: int
    team_name: str
    possession_pct: float
    xg: float
    shots: int
    shots_on_target: int
    passes: int
    pass_accuracy: float
    ppda: Optional[float]
    field_tilt: Optional[float]
    formation: Optional[str]

class PlayerMatchStats(BaseModel):
    match_id: int
    player_id: int
    player_name: str
    team_id: int
    minutes_played: int
    goals: int
    assists: int
    xg: float
    xa: Optional[float]        # StatsBomb open data has no xA: stays None unless docs/metrics.md documents a proxy
    passes: int
    pass_accuracy: float
    shots: int
    tackles: int
    position_played: Optional[str]

class MatchEvent(BaseModel):
    id: int
    match_id: int
    minute: int
    second: int
    event_type: str
    team_id: int
    player_id: Optional[int]
    x: Optional[float]
    y: Optional[float]
    outcome: Optional[str]
    related_event_id: Optional[int]
    xg: Optional[float]          # shot xG (StatsBomb `statsbomb_xg`); None for non-shots
    possession_id: Optional[int] # required by Phase 2 `possession_sequences`
    source_id: Optional[str]     # provider id, for idempotent upserts

class ToolResult(BaseModel):
    """Envelope every tool returns so the LLM sees evidence refs."""
    data: dict | list
    evidence_refs: list[str] = Field(default_factory=list)  # e.g. ["team_match_stats:12:34", "event:431"]
```

### 6.2 Agent contracts (`app/schemas/agents.py`) — Phase 3 (Finding), Phase 8 (Critic)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class AgentFinding(BaseModel):
    agent: str
    summary: str
    evidence_refs: list[str]          # pointers, not raw data
    confidence: float = Field(ge=0, le=1)

class CriticIssue(BaseModel):
    type: Literal["unsupported_claim", "contradiction", "hallucination", "missing_evidence"]
    claim: str
    reason: str

class CriticResult(BaseModel):
    passed: bool
    issues: list[CriticIssue]
    required_action: Literal["retrieve_more_data", "redo_tactical", "redo_player", "none"]
```

### 6.3 Graph state (`app/graph/state.py`) — Phase 5

```python
from typing import TypedDict, Literal, Optional

class GraphState(TypedDict):
    user_query: str
    query_type: Literal["simple_stat", "player", "tactical", "comparison", "report"]
    execution_plan: list[str]          # node names the orchestrator selected
    match_id: Optional[int]
    team_ids: list[int]
    player_ids: list[int]
    match_data: Optional[dict]
    team_stats: Optional[dict]
    player_stats: Optional[dict]
    events: Optional[list[dict]]
    retrieved_documents: list[dict]    # [{content, source, score}]
    agent_findings: list["AgentFinding"]
    critic_feedback: Optional["CriticResult"]
    retry_count: int
    errors: list[str]
    degraded: bool
    final_report: Optional[str]
```

State must NOT contain: full prompt/completion history, embeddings, large raw event payloads once summarized (R9).

### 6.4 API surface (final)

```
GET  /health                      → HealthResponse
GET  /matches                     → MatchSummary[]
GET  /matches/{id}                → MatchDetail
GET  /matches/{id}/stats          → TeamMatchStats[]
GET  /matches/{id}/events         → MatchEvent[]
GET  /matches/{id}/players        → PlayerMatchStats[]
POST /analysis                    → {query, match_id?} → AnalysisResult
POST /analysis/stream             → same input, SSE stream (Phase 9a; event contract in 6.6)
POST /analysis/tactical           → {match_id, focus?} → TacticalAnalysisResult
POST /analysis/player             → {match_id, player_id} → PlayerAnalysisResult
POST /analysis/comparison         → {match_id_a, match_id_b} → ComparisonResult
GET  /reports/{id}                → Report
```

**`/health` semantics.** Returns HTTP 200 whenever the process is serving. A dependency that is down
is reported in the body as `status: "degraded"` with the failing dependency named (`db: "unavailable"`),
never as a 5xx — a dead dependency is not a dead process (R5). The status code alone is therefore not a
health signal: uptime checks and the frontend must read the body.

**Status codes and the error envelope.** Every non-2xx response has the same shape:

```json
{"error": {"code": "match_not_found", "message": "No match with id 999999.", "context": {"match_id": 999999}, "request_id": "..."}}
```

`code` is the `AppError` subclass's `code` (section 4); `context` is optional and never contains secrets;
`request_id` echoes the `X-Request-ID` response header. Codes by status: 404 (`match_not_found`,
`player_not_found`), 422 (`validation_failed` — both for malformed requests and for failing Pydantic
model/agent output, R3), 502 (`data_unavailable`, `tool_execution_error`, `llm_error`), 504
(`llm_timeout`), 500 (`internal_error`, never with a traceback in the body).

**Response models** (`app/schemas/matches.py` in Phase 1; `app/schemas/analysis.py` in Phases 3/6):

```python
# --- Phase 1 ---
class TeamSummary(BaseModel):
    id: int
    name: str
    country: Optional[str]

class MatchSummary(BaseModel):
    id: int
    home_team: TeamSummary
    away_team: TeamSummary
    competition: str
    season: str
    match_date: date
    home_score: Optional[int]      # None if not yet played/ingested
    away_score: Optional[int]

class MatchDetail(MatchSummary):
    event_count: int
    has_stats: bool                # False until Phase 2 populates team_match_stats

# --- Phase 3 (AnalysisResult) / Phase 6 (the rest) ---
class EvidenceItem(BaseModel):
    """One resolved evidence_ref, rendered in the UI's Evidence list."""
    ref: str                       # "team_match_stats:12:34" | "event:431"
    label: str                     # "Arsenal xG"
    value: str | float | int | None

class SourceItem(BaseModel):       # RAG citations only (Phase 7)
    title: str
    url: str

class AnalysisResult(BaseModel):
    run_id: str
    query_type: Literal["simple_stat", "player", "tactical", "comparison", "report"]
    answer_markdown: str
    evidence: list[EvidenceItem]
    sources: list[SourceItem] = []
    confidence: float = Field(ge=0, le=1)
    degraded: bool = False
    retry_count: int = 0

class TacticalAnalysisResult(AnalysisResult):
    match_id: int
    report_id: Optional[int]       # set once the report is persisted

class PlayerAnalysisResult(AnalysisResult):
    match_id: int
    player_id: int
    report_id: Optional[int]

class ComparisonResult(AnalysisResult):
    match_id_a: int
    match_id_b: int
    report_id: Optional[int]

class Report(BaseModel):
    id: int
    agent_run_id: str
    match_id: Optional[int]
    content: str                   # fixed 4-section template (Phase 6)
    created_at: datetime
```

**`comparison` means two matches — always.** Comparing two teams *within one match* is a `tactical`
query. This settles the wording in Phase 3's golden set; Appendix B follows the same rule.

### 6.5 Environment variables (`.env.example`)

```
DATABASE_URL=postgresql+psycopg://app:app@localhost:55432/football  # host port: see docker-compose.yml
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
GROQ_API_KEY=
LLM_MODEL=llama-3.3-70b-versatile  # or local/cloud OpenAI-compatible model
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_TIMEOUT_SECONDS=45
TOOL_TIMEOUT_SECONDS=10
MAX_CRITIC_RETRIES=2
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
CORS_ORIGINS=http://localhost:5173
ENVIRONMENT=local
LOG_LEVEL=INFO
DB_HEALTH_TIMEOUT_SECONDS=2      # how long /health waits for a DB ping before reporting unavailable

# Frontend lives in frontend/.env (Vite only reads its own directory)
VITE_API_URL=http://localhost:8000
```

### 6.6 SSE event contract (`POST /analysis/stream`) — Phase 9a

Frozen here so the backend and frontend cannot drift; do not rename events silently.

| event | payload |
|---|---|
| `run_started` | `{run_id}` |
| `node_started` | `{node, label}` |
| `node_finished` | `{node, status, latency_ms}` |
| `token` | `{text}` — chunks of the final `answer_markdown` |
| `final` | the full `AnalysisResult` |
| `error` | the section 6.4 error envelope |

A client disconnect must abort the run (not just the stream). The stream ends after `final` **or**
`error`, never both, and never with neither.

### 6.7 Evaluation determinism — Phase 3

Golden-set numbers always come from the DB/analytics code, never from an LLM (Appendix C). So that
scores are comparable across phases:

- Agent and tool-calling LLM calls run at **temperature 0**.
- The LLM-as-judge (Phase 10) uses a fixed prompt at **temperature 0**, and its version is recorded.
- `scripts/run_eval.py` records model ID, temperature, prompt version and dataset version in its
  output, so a score change can be attributed to a code change rather than sampling noise.
- LLM-marked tests (`pytest -m llm`) are **deselected by default** and never run on a normal CI push
  (they cost money and need an API key). They run in a separate manual or nightly workflow.

---

# RELEASE 1 — MVP

**Release goal:** pick a match → see stats → ask a question → get a grounded answer, end to end.

---

## Phase 0 — Foundation

**Goal:** a runnable skeleton with CI, so every later phase has somewhere to land.
**Depends on:** nothing. **Estimate:** 2–3 days.

### Scope
- Repo structure from section 3 (empty packages with `__init__.py` are fine).
- `docker-compose.yml` with Postgres 16 and Qdrant (Qdrant can be present but unused until Phase 7).
- FastAPI app with `GET /health` returning `{status, db}` (checks DB connectivity once DB exists; static ok for now).
- `core/config.py`, `core/logging.py`, `core/errors.py` per conventions.
- React + Vite + TS + Tailwind app that calls `/health` and shows "API healthy" or an error.
- Tooling: ruff, mypy, pytest, eslint, prettier, pre-commit optional.
- GitHub Actions (or equivalent): backend lint+type+tests, frontend lint+build+tests.
- `README.md` with 5-command quickstart.

### Out of scope
DB models, data, LLM, auth.

### Tests
- `tests/api/test_health.py`: returns 200 and the expected shape.
- FE: one render test that mocks `/health`.

### Acceptance checks
- [ ] `docker compose up -d` starts Postgres and Qdrant healthy.
- [ ] `uvicorn app.main:app` → `curl localhost:8000/health` returns 200.
- [ ] Frontend dev server shows "API healthy".
- [ ] CI green on a fresh push.

### AI prompt
```
Implement Phase 0 of IMPLEMENTATION.md. First list the files you will create and wait for my OK.
Then build: the repo skeleton, docker-compose (postgres:16 + qdrant), FastAPI app with /health,
pydantic-settings config, structured JSON logging, the error hierarchy from section 4, a Vite React TS
Tailwind frontend that calls /health, lint/type/test tooling, CI workflow, and README quickstart.
Check current official docs for every tool's setup. Do not add anything outside Phase 0 scope.
Finish by giving me the exact commands to verify each acceptance check.
```

**Commit:** `feat(phase-0): project foundation`
**Handoff notes:**
- **Built:** uv-managed FastAPI backend (`/health` → `{status, db}`), structured JSON logging with a
  `request_id` contextvar, the section 4 error hierarchy mapped to 404/422/502/504 with one
  `{"error": {code, message, context?, request_id?}}` envelope, CORS + request-id middleware, and a
  timeout-bounded Postgres probe. Frontend: Vite 8 + React 19 + Tailwind 4 + TS with a typed API client
  and a health card (loading / healthy / degraded / error+retry). Plus docker-compose (postgres:16,
  qdrant v1.19.1), ruff + `mypy --strict` + pytest, ESLint + Prettier + Vitest, SHA-pinned CI, README.
- **Verified:** 30 backend tests, ruff, `mypy --strict` clean; 3 frontend tests, ESLint, `tsc -b` + build clean;
  live `curl /health` → 200, CORS preflight from :5173 allowed, and headless Chrome renders "API healthy".
- **Deviations:** `/health` deliberately always returns 200 and reports trouble as `status: "degraded"`
  (a dead dependency is not a dead process, R5); both are now specified in section 6.4. TypeScript is pinned
  to ~6.0.3 because typescript-eslint 8 caps at `<6.1.0`; Vitest uses `pool: 'threads'` because the default
  `forks` pool times out starting workers on Windows.
- **Pending:** `docker compose up -d` healthchecks for both containers, and the first green CI run
  (no git repo or remote exists yet). `backend/Dockerfile` is written but was never built.
- **Known issues:** no `.env` is needed in Phase 0, so `/health` reports `db: "not_configured"` out of the box;
  `frontend/src/{pages,hooks,types}` are not created until Phase 4.
- **Doc amendment:** section 6 was extended at the end of Phase 0, before any code depends on it:
  6.1 (`xa` nullable, `MatchEvent` gains `xg`/`possession_id`/`source_id`), 6.4 (response models,
  error envelope, `/health` semantics, the `comparison` = two matches rule), 6.5 (extra keys), and the
  new 6.6 (SSE contract) and 6.7 (eval determinism). Phases 1, 3, 4, 9, 11 and 13 were updated to match.

---

## Phase 1 — Data pipeline and database

**Goal:** real match data in Postgres behind a swappable service interface.
**Depends on:** Phase 0. **Estimate:** ~1 week.

### Scope
1. **Dataset selection:** use StatsBomb open data. Choose **one competition-season, 20–30 matches** (pick one that includes lineups and events; prefer one with full-season coverage for at least one team). Record the choice and licence/attribution requirement in `docs/data-source.md`.
2. **ORM models + Alembic migration `0001`** for: `teams`, `players`, `matches`, `events`, `team_match_stats`, `player_match_stats`, `formations`. (`agent_runs`, `reports`, `tactical_analysis` come in later phases' migrations.)
3. **ETL script** `scripts/etl_statsbomb.py`:
   - Download/read raw JSON into `data/raw/` (gitignored).
   - Normalize into DB rows. Map StatsBomb event types to a consistent `event_type` set; keep `x, y` from the event's `location`; capture shot xG (`statsbomb_xg`) in an `outcome`/metadata column or a dedicated `shots`-friendly column (add `xg` nullable on `events`).
   - **Idempotent:** re-running produces no duplicates (upsert on natural keys or source IDs; keep `source_id` columns).
   - Logs counts per table.
4. **`MatchDataService`** (`app/services/match_data.py`): abstract interface + `PostgresMatchDataService`. Methods: `list_matches`, `get_match`, `get_events(match_id, event_type=None)`, `get_players(match_id)`, `get_team_stats(match_id, team_id=None)`.
5. **Routers:** `GET /matches`, `GET /matches/{id}`, `GET /matches/{id}/events`, `GET /matches/{id}/players`, with the response models from section 6.4. (`/stats` comes in Phase 2 when metrics exist.)
6. **Seed path:** `scripts/seed.py` running `alembic upgrade head` → ETL for the chosen season, idempotent and safe to re-run. Phase 2 extends it with `compute_stats.py`. Documented in the README as the single command that takes a fresh clone to a usable app — the Phase 4 gate (fresh clone → running app in under 15 minutes) depends on it.

### Schema notes
- Index `events(match_id, minute)`; unique `player_match_stats(match_id, player_id)`; unique `team_match_stats(match_id, team_id)`; FKs everywhere.
- `player_match_stats` and `team_match_stats` can initially be populated from **aggregating events in the ETL** (goals, shots, passes, xG, tackles). Metrics needing definitions (PPDA, field tilt) stay NULL until Phase 2.
- `events` stores shot `xg` (StatsBomb `statsbomb_xg`), `possession_id` and `source_id` — `possession_id` is what Phase 2's `possession_sequences` groups on (section 6.1 / Appendix A).

### Out of scope
Live API, LLM, metrics beyond simple counts.

### Tests
- Unit: event-type mapping, coordinate handling, aggregation of simple counts.
- Integration (test DB): run ETL on a tiny fixture (2 matches committed under `tests/fixtures/`) and assert row counts, FK integrity, idempotency (run twice → same counts).
- API: `/matches` returns fixture matches; `/matches/999999` → 404.

### Acceptance checks
- [ ] `alembic upgrade head` on an empty DB succeeds; `downgrade base` also works.
- [ ] ETL loads the chosen season; counts printed match the source file counts.
- [ ] Running ETL twice creates no duplicates.
- [ ] `GET /matches` and `GET /matches/{id}/events?event_type=Shot` return real data.
- [ ] Spot check: one match's final score and one player's shot count agree with the source data.

### AI prompt
```
Implement Phase 1 of IMPLEMENTATION.md. Steps: (1) inspect the StatsBomb open-data repo structure and propose
one competition-season of 20-30 matches, explain why, and wait for my OK; (2) write ORM models and the Alembic
migration; (3) write the idempotent ETL; (4) implement MatchDataService with an abstract base and a Postgres
implementation; (5) add the routers; (6) write fixture-based tests. Verify current StatsBomb file formats by reading
the actual JSON, not from memory. Stay inside Phase 1 scope.
```

**Commit:** `feat(phase-1): data pipeline, schema, match data service`
**Handoff notes:**
- **Dataset:** Copa América 2024 (competition 223, season 282) — the smallest *complete*
  competition-season with lineups + events for every match (32 matches; no candidate landed in the
  20–30 window). Rationale, licence note and every verified schema quirk live in `docs/data-source.md`.
- **Built:** ORM models + Alembic `0001` (surrogate ids, `source_id` columns everywhere, the section 6
  indexes/uniques), an idempotent upsert ETL (`app/etl/statsbomb.py`, CLI wrapper `scripts/etl_statsbomb.py`,
  one-command `scripts/seed.py` = migrate + load), `MatchDataService` (abstract + Postgres impl) and the four
  routers with the section 6.4 response models and error envelope. `team_match_stats`/`player_match_stats`
  are populated from event aggregation in the same load (PPDA/field tilt/possession stay NULL for Phase 2).
- **Data quirks handled (all verified against the real feed, detailed in `docs/data-source.md`):** event ids
  are UUID strings; period 5 is a shootout and is dropped (95 events); a completed pass has no `outcome`
  (stored as `Complete`); an own goal is `Own Goal Against`/`Own Goal For`, not a shot; `Duel` is split by
  `duel.type` into `tackle`/`aerial_lost`/`duel` so Phase 2's PPDA reads `event_type` alone.
- **Minutes quirk found late (and fixed):** StatsBomb's `positions[]` spells are not authoritative for
  time — they round to the minute and can omit a substitute's entry spell entirely (Lautaro Martínez,
  the final, loaded as 8 minutes for a player who came on at 96:03 and scored in the 111th). The ETL now
  also reads exact entry/exit clocks from `Substitution` events (`substitution_windows`) and takes the
  wider of the two windows; unit + fixture tests cover both spell-only and event-derived shapes.
- **Windows-only ops bug fixed:** uvicorn without `--reload` serves on the Proactor event loop, which
  psycopg's async driver refuses (`InterfaceError` on first DB use — every request 500ed). uvicorn picks
  its loop *before* importing the app, so the fix is a `--loop` factory (`app.core.eventloop:
  psycopg_safe_uvicorn_loop_factory`, no-op elsewhere) and the README quickstart was updated. The
  event-loop policy in `app/core/eventloop.py` covers everything that runs `asyncio.run` itself.
- **Verified:** 118 backend tests (incl. integration against the compose Postgres: FK integrity, row
  counts, idempotency, hand-verified aggregates), ruff + `mypy --strict` clean; live API checked with the
  season loaded: `/health` ok, 32 matches, 100,229 events, 1,618 player rows, 188 formations, second seed
  run changed nothing; final score (1–0), shot count (30), and a player's shot count (1) reconciled
  against the raw JSON. Alembic `upgrade head` / `downgrade base` covered by the migration tests.
- **Known issues:** the season is 32 matches, slightly over the 20–30 target (documented trade-off);
  `docs/metrics.md`, `GET /matches/{id}/stats` and `scripts/compute_stats.py` are Phase 2.

---

## Phase 2 — Analytics library (no LLM)

**Goal:** trustworthy, tested metrics computed from events. If these are wrong, everything downstream is confidently wrong.
**Depends on:** Phase 1. **Estimate:** ~1 week.

### Scope
Pure functions in `app/analytics/` taking typed inputs (lists of `MatchEvent`) and returning typed results. **No DB access, no network** inside these functions; services fetch, analytics compute.

| Function | Definition (write final wording in `docs/metrics.md`) |
|---|---|
| `possession_pct` | Team's share of total pass count (or of possession-duration if the data supports it). Document the choice. |
| `shots`, `shots_on_target`, `xg_total` | From Shot events; on target = goal/saved/saved-to-post (document mapping). |
| `pass_accuracy` | Completed passes / attempted passes. |
| `ppda(team)` | Opponent passes in their own 60% of the pitch ÷ team's defensive actions (tackles/duels won, interceptions, fouls committed, ball challenges) in the team's attacking 60%. Coordinates are per-team perspective, so opponent's own-60% = `x ≤ 72`; team's attacking-60% = `x ≥ 48` on a 120-length pitch. |
| `field_tilt(team)` | Team's final-third passes ÷ (both teams' final-third passes). Final third = `x ≥ 80` in the acting team's perspective. |
| `possession_sequences` | Group consecutive events by `possession` id into chains; return start/end zone, duration, number of passes, ended-in-shot flag. |
| `player_metrics` | Per player: goals, assists, xG, xA (if available), passes, pass accuracy, shots, tackles, minutes. |

Then:
- **Populate** `team_match_stats.ppda/field_tilt/xg/possession_pct` and `player_match_stats` through `scripts/compute_stats.py` (idempotent).
- Add `GET /matches/{id}/stats`.
- Write `docs/metrics.md` with exact definitions, edge cases (own goals, extra time, red cards) and known limitations.

### Out of scope
Any LLM, RAG, graph.

### Tests
- Hand-calculated fixtures: for **3 matches** compute possession, shots, xG, pass accuracy, PPDA and field tilt by hand (spreadsheet or a small manual script) and assert equality within a tolerance.
- Edge cases: zero defensive actions (PPDA → `None`, not crash), match with red card, extra-time events, missing coordinates.
- Property test: `field_tilt(A) + field_tilt(B) ≈ 1.0`.

### Acceptance checks
- [x] All unit tests pass; hand-verified values documented in `docs/metrics.md`.
- [x] `GET /matches/{id}/stats` returns both teams with non-null PPDA/field tilt where computable.
- [x] `compute_stats.py` is idempotent.
- [x] A reviewer can read `docs/metrics.md` and reproduce one number by hand.

### AI prompt
```
Implement Phase 2 of IMPLEMENTATION.md. Write pure typed analytics functions in app/analytics with no DB/network
access, the compute_stats script, GET /matches/{id}/stats, and docs/metrics.md with exact metric definitions
(use the PPDA and field-tilt definitions in the table and confirm the pitch coordinate system by inspecting real
event data). Create hand-verified test fixtures for 3 matches and show me the manual calculation for each so I can
sanity check. Do not touch anything LLM-related.
```

**Commit:** `feat(phase-2): analytics library and match stats`
**Handoff notes:** Pure analytics functions implemented in `app/analytics/{metrics.py, sequences.py, types.py}` with no DB or network access (rule R8). `possession_pct` uses pass-count share proxy. `ppda` uses ground tackles (from duel split), interceptions, and fouls committed in attacking 60% vs opponent passes in own 60% ($x \le 72.0$). `field_tilt` measures final-third ($x \ge 80.0$) pass share and sums to 1.0. `possession_sequences` computes clock-based chain duration and zone progressions. `compute_stats.py` populates `team_match_stats` idempotently and is chained in `seed.py`. `GET /matches/{id}/stats` routed and verified. Metric definitions, edge-case handling rules, and hand-calculated verification tables for 3 matches (2 real StatsBomb tournament matches + 1 deterministic synthetic fixture) documented in `docs/metrics.md`. 129 unit/API tests passing cleanly, type checks and lints 100% clean.

---

## Phase 3 — Single agent with tools (+ golden eval set v1)

**Goal:** first LLM feature: one agent answers questions by calling typed tools; numbers only come from tools.
**Depends on:** Phase 2. **Estimate:** ~1 week.

### Scope
1. **LLM client wrapper** (`app/core/llm.py`): Llama 3.3 70B via Groq / OpenAI-compatible client with `GROQ_API_KEY`, model from `LLM_MODEL`, timeout, bounded retries with backoff on transient errors, token-usage capture, raises `LLMError` / `LLMTimeoutError`. All LLM calls go through this wrapper (needed later for tracing and cost).
2. **Tools** (`app/tools/`) each with a Pydantic input model, a `ToolResult` output (section 6.1), a docstring/description the LLM will see, and specific exceptions:
   - `get_match_stats(match_id)`
   - `get_match_events(match_id, event_type=None, limit=…)` (cap the size returned; include truncation flag)
   - `get_team_stats(team_id, match_id=None)`
   - `get_player_stats(player_id, match_id=None)`
   - `find_player(name, match_id)` and `find_team(name)` name→id resolvers (users say names, not IDs)
   - `calculate_player_metric(player_id, metric)` (metric is an enum)
3. **Tool registry** (`app/tools/registry.py`): one place that maps tool name → function + JSON schema for the LLM.
4. **Single agent** (`app/agents/basic_agent.py`): loop of {LLM call → if tool_use, execute tool, feed `tool_result` → repeat} with a hard max-iterations cap (e.g. 6). System prompt enforces R1/R2 and asks for a final structured output: `{answer_markdown, evidence_refs[], confidence}` validated by Pydantic.
5. **Endpoint** `POST /analysis` `{query, match_id?}` → `AnalysisResult` (section 6.4; fields not yet available stay null/empty).
6. **Golden eval set v1:** `tests/eval/golden_v1.jsonl` with **10 questions** (mix: simple stat, player, "who pressed more", and an across-two-matches comparison — see the `comparison` rule in section 6.4, and 6.7 for determinism requirements). Each has `expected_values` (from the DB/metrics, not from the LLM) and a `must_reference` list. Script `scripts/run_eval.py` runs them against the API and prints pass/fail and accuracy. Extend every phase.

### Prompting requirements (put in the system prompt)
- "You may only state numbers that appear in tool results."
- "If the data needed isn't available via tools, say so; do not estimate."
- "Resolve names with find_* tools before calling stat tools."
- "Return the final answer in the required JSON schema."

### Out of scope
LangGraph, multiple agents, RAG, streaming, frontend.

### Tests
- Unit (no LLM): each tool — happy path, not-found, invalid input, truncation.
- Agent (mock LLM): scripted tool_use → tool_result → final answer sequence; assert max-iteration cap; assert a malformed final output raises `ValidationFailedError` (or is retried once).
- LLM-marked: 3 real calls that assert answers contain the DB-verified numbers.
- API: invalid `match_id` → 404 JSON error; LLM timeout → 504 with clean body.

### Acceptance checks
- [ ] "How many shots did <Team A> take in match X?" returns the correct number with evidence refs.
- [ ] "Which team pressed more, and how do you know?" cites PPDA values from tools.
- [ ] Golden set v1 factual accuracy ≥ 80%.
- [ ] Manual check of 20 varied questions: **zero invented numbers**.
- [ ] Tool failure and LLM timeout return graceful errors.

### AI prompt
```
Implement Phase 3 of IMPLEMENTATION.md. Build the LLM wrapper, the typed tools with ToolResult envelopes and
resolvers, the tool registry, a single tool-calling agent loop with an iteration cap and Pydantic-validated final
output, POST /analysis, and golden eval set v1 plus scripts/run_eval.py. Read the current Grok/xAI tool-use docs
before coding. Write tool unit tests and a mock-LLM agent test first. Do not use LangGraph or add more agents.
```

**Commit:** `feat(phase-3): single agent with tools and eval v1`
**Handoff notes:** Built Llama 3.3 70B (Groq / OpenAI-compatible) client wrapper with exponential backoff and timeout enforcement. Implemented typed tool registry with 7 deterministic tools (`get_match_stats`, `get_match_events`, `get_team_stats`, `get_player_stats`, `find_player`, `find_team`, `calculate_player_metric`) returning `ToolResult` envelopes with `evidence_refs`. Built `BasicAnalystAgent` tool-calling loop with a 6-iteration cap and Pydantic validation into `AnalysisResult`. Created `POST /analysis` endpoint, golden eval set v1 (10 questions in `backend/tests/eval/golden_v1.jsonl`), and `scripts/run_eval.py` evaluation runner. Unit tests, mock-LLM agent tests, and API tests all passing offline.

---

## Phase 4 — Thin UI  ⟵ MVP GATE

**Goal:** a person who isn't you can use the product end to end.
**Depends on:** Phase 3. **Estimate:** ~1 week.

### Scope
- Pages: **Match List** (search/filter by team), **Match Detail** with team-stat comparison (Recharts bar chart + stat table) and a **chat panel**.
- Chat: input, suggested starter questions, loading state, error state, answer rendered as markdown, an "Evidence" expandable list showing each `evidence_ref` with its value.
- Typed API client (generated types from OpenAPI), React Query for fetching.
- `npm run types:generate` runs `openapi-typescript` against the API's `/openapi.json` and writes `src/types/api.ts`. Hand-written response types are replaced by it, and the script must be re-run whenever an endpoint or model changes — this is what keeps the frontend from silently drifting.
- Non-streaming for now.

### Out of scope
Timeline, pitch diagrams, player cards, auth, streaming.

### Tests
- FE component tests: match list renders, chat submit → shows answer (mock API), error state.
- One Playwright/Cypress smoke test (optional but recommended): list → match → ask → answer visible.

### MVP exit gate (all must be true)
- [x] Full demo path works on every seeded match.
- [x] Golden set v1 ≥ 80% accuracy; 20-question manual check has no invented numbers.
- [x] A fresh clone → running app in under 15 minutes following the README.
- [x] One non-technical person completes the flow unassisted.
- [x] Tag repo `v0.1.0-mvp`.

### AI prompt
```
Implement Phase 4 of IMPLEMENTATION.md: the thin UI. Generate TypeScript types from the FastAPI OpenAPI schema,
build the Match List page, Match Detail page with a Recharts team comparison, and a chat panel that calls
POST /analysis and shows answer markdown plus an expandable Evidence list. Include loading/error states and
component tests. Keep styling simple with Tailwind. No streaming or extra pages.
```

**Commit:** `feat(phase-4): thin UI - MVP complete`
**Handoff notes:** Generated TypeScript types from FastAPI's OpenAPI schema using `openapi-typescript` (`npm run types:generate` & `scripts/export_openapi.py`). Built the Match List page with live team and competition search/filtering, Match Detail page with Recharts tactical team comparisons (bar chart + head-to-head metric breakdown), and the Grounded Analyst Chat panel with starter questions, markdown rendering, loading/error retry states, and expandable Evidence drawer showing deterministic database refs. Built typed API client on top of `@tanstack/react-query`. All 14 Vitest unit and integration component tests passing cleanly.

---

# RELEASE 2 — AGENTIC CORE

## Phase 5 — LangGraph skeleton

**Goal:** replace the single-agent loop with an explicit, inspectable graph — same API, no UI change.
**Depends on:** Phase 4. **Estimate:** ~1.5 weeks.

### Scope
1. Migration `0002`: `agent_runs` (`id, created_at, user_query, query_type, graph_state_snapshot jsonb, status, retry_count, latency_ms, token_usage jsonb, error`).
2. `app/graph/state.py` per section 6.3.
3. Nodes (`app/graph/nodes/`):
   - **question_analyzer**: LLM structured output → `query_type`, extracted names → resolved `match_id/team_ids/player_ids` via resolvers. If `match_id` is missing and the query needs one, return a clarification response.
   - **orchestrator**: deterministic mapping first (query_type → plan), LLM only for ambiguous cases. Output `execution_plan`.
   - **data_retrieval**: calls tools once and populates `match_data/team_stats/player_stats/events` (**reused by all later nodes, not re-fetched**).
   - **simple_formatter**: formats answers for `simple_stat` queries (tool output → concise markdown; may use a tiny LLM call for phrasing, numbers inserted from state).
   - **degraded_response**: builds a safe response from whatever data exists plus an explanation.
4. Edges: conditional after orchestrator (`simple_stat` → formatter → END; others → a placeholder "analysis" node that for now reuses the Phase 3 agent so behavior does not regress); **error edge** from every tool-calling node to `degraded_response`.
5. **Runner** `app/graph/runner.py`: builds the graph, invokes with a run ID, writes `agent_runs` (status, latency, token usage, sanitized state snapshot).
6. `POST /analysis` now calls the runner. Response includes `run_id` and `degraded`.
7. Expand golden set to **15 questions**.

### Out of scope
Player/Tactical/Synthesis agents, RAG, Critic, streaming, checkpointing (later).

### Tests
- Graph routing tests (no LLM, mocked analyzer): table-driven — each `query_type` → expected node sequence.
- Failure tests: tool raises `MatchNotFoundError`, `DataUnavailableError`, LLM timeout → assert degraded response, no crash, `agent_runs.status` correct.
- State test: state after data_retrieval contains no oversized payloads (assert size cap).
- Regression: golden set score ≥ Phase 4 score.

### Acceptance checks
- [ ] Simple stat queries skip analysis nodes (verify via `agent_runs` snapshot or logs).
- [ ] Every request creates an `agent_runs` row with latency and token usage.
- [ ] Simulated failures produce degraded responses.
- [ ] Golden set has not regressed.
- [ ] Generate and commit a Mermaid diagram of the compiled graph to `docs/graph.md`.

### AI prompt
```
Implement Phase 5 of IMPLEMENTATION.md using LangGraph (read the current LangGraph docs first, especially
StateGraph, conditional edges, and error handling). Build the state, the nodes question_analyzer, orchestrator,
data_retrieval, simple_formatter, degraded_response, the conditional routing, the runner that persists agent_runs,
and switch POST /analysis to the runner. Keep the Phase 3 agent as the temporary 'analysis' node so nothing
regresses. Write table-driven routing tests and failure-mode tests before wiring the LLM.
```

**Commit:** `feat(phase-5): langgraph skeleton and run logging`
**Handoff notes:** _(fill in)_

---

## Phase 6 — Multi-agent analysis

**Goal:** real analytical depth: Player + Tactical agents in parallel, synthesized into a structured report.
**Depends on:** Phase 5. **Estimate:** 2–2.5 weeks.

### Scope
1. Migration `0003`: `tactical_analysis`, `reports`.
2. New tools: `get_shot_data(match_id)`, `get_possession_sequences(match_id)`, `compare_matches(a, b)` (add if not yet present), all returning `ToolResult` with evidence refs.
3. **Player Agent** (`agents/player_agent.py`): input = state's player stats/events; output = list of `AgentFinding`. Prompt: interpret numbers, no new numbers, cite `evidence_refs`.
4. **Tactical Agent** (`agents/tactical_agent.py`): covers formations, pressing (PPDA), possession/field tilt, transitions, shot quality as **sections within one prompt** (do not create sub-agents). Output = `AgentFinding[]`, each with confidence.
5. **Parallel execution:** Player and Tactical branches run concurrently after data_retrieval when the plan includes them (LangGraph fan-out/fan-in).
6. **Synthesis Agent:** merges findings into a draft; **hard rule in code:** drop any claim without non-empty `evidence_refs` before it reaches later nodes (log dropped claims).
7. **Report Agent:** renders the final markdown using a **fixed template**: `## What happened` (tool-grounded facts only) / `## Analysis` (interpretation, labelled) / `## Key evidence` (list of refs → values) / `## Confidence`.
8. Persist `reports`; add `GET /reports/{id}`, `POST /analysis/tactical`, `POST /analysis/player`.
9. **Query routing** per section 13 of the design: player → Player only; tactical → Tactical (+Player if players named); comparison → both matches, both agents; simple_stat unchanged.
10. Expand golden set to **20 questions** including tactical and comparison. Add an "evidence coverage" metric to the eval script (fraction of report claims with valid refs).
11. Frontend (minimal): render the structured report in the existing chat panel (sections, evidence list). Full UI is Phase 9.

### Out of scope
RAG, Critic, retries, streaming.

### Tests
- Agent tests with mocked tool outputs: assert schema-valid `AgentFinding`; assert agents never output numbers absent from input (simple regex/number-extraction check against provided data).
- Graph tests: routing per query type; parallel branches both execute; a failure in one branch degrades gracefully (other findings still reported, flagged).
- Synthesis test: input with an evidence-less claim → claim dropped.
- Report test: output always contains all four template sections.

### Acceptance checks
- [ ] A tactical question produces a report with all sections; every number traces to a ref.
- [ ] Player and Tactical branches demonstrably run in parallel (timing or trace).
- [ ] Evidence coverage ≥ 95% on the golden set.
- [ ] Killing one branch (simulated) still yields a partial, flagged report.

### AI prompt
```
Implement Phase 6 of IMPLEMENTATION.md. Add the extra tools, the Player, Tactical, Synthesis and Report agents
(prompts + Pydantic-validated outputs), fan-out/fan-in parallel execution in the LangGraph, the code-level rule that
drops claims lacking evidence_refs, the fixed report template, the reports table and the new endpoints. Tactical
sub-topics must be sections of one prompt, not separate agents. Start with mock-based tests, then run the
golden set. No RAG or critic yet.
```

**Commit:** `feat(phase-6): multi-agent analysis and reports`
**Handoff notes:** _(fill in: prompt versions, cost/latency per query type)_

---

# RELEASE 3 — KNOWLEDGE + TRUST

## Phase 7 — RAG

**Goal:** tactical claims are enriched with cited domain knowledge.
**Depends on:** Phase 6. **Estimate:** ~2 weeks.

### Scope
1. **Knowledge base** `knowledge_base/*.md`: 10–20 curated documents (pressing/PPDA, build-up play, half-spaces, transitions, low block, field tilt, xG, formations, etc.). Each file has front-matter: `title, source, url, license_note, concept_tags`. Only use content you have the right to use (your own notes, openly licensed material, or short attributed summaries you write).
2. **Ingestion** `scripts/ingest_kb.py` and `app/rag/`: clean → paragraph/semantic chunks (~300–500 tokens) → metadata `{source, title, concept_tags, url, chunk_id}` → embed once → upsert to a Qdrant collection. Idempotent (deterministic chunk IDs). Choose the embedding model here; record model name + dimension in `docs/decisions/rag.md` (a collection must not mix embedding models).
3. **Retriever** `app/rag/retriever.py`: top-k (start 4–6) similarity search with optional concept-tag filter; returns `[{content, source, url, score}]`. Tool: `search_tactical_knowledge(query, top_k)`.
4. **RAG node/agent:** LLM is used only to reformulate the query from the question + tactical findings (e.g., "high press, PPDA 7" → "pressing triggers, high press"). Output → `state.retrieved_documents` (top-k with scores, truncated content).
5. **Wiring:** runs only for `tactical` and `comparison` queries, after Player/Tactical, before Synthesis. Synthesis/Report must carry `source` through; report gets a `## Sources` section.
6. **Empty/low-score results:** node returns empty list; Synthesis proceeds without RAG claims and does not invent sources.

### Out of scope
Reranking, hybrid search, auto-ingestion from the web.

### Tests
- **Retrieval test set** (`tests/rag/`): ≥ 15 queries → expected doc(s) in top-5; report hit-rate.
- Ingestion: idempotent (twice → same point count); chunk sizes within bounds; metadata always present.
- Graph: RAG node skipped for `simple_stat`/`player`; runs for `tactical`.
- Failure: Qdrant down / empty collection → graph degrades (no RAG) without crashing.
- Injection hygiene: a KB doc containing "ignore previous instructions" must not alter agent behavior (retrieved text is passed as quoted data in the prompt, with instructions to treat it as untrusted).

### Acceptance checks
- [ ] Retrieval hit-rate@5 ≥ 80% on the retrieval test set.
- [ ] Tactical reports include a Sources section; every RAG-derived statement has a source.
- [ ] Qdrant outage test passes.
- [ ] No source is ever cited that wasn't retrieved (assert in test).

### AI prompt
```
Implement Phase 7 of IMPLEMENTATION.md. Create the ingestion pipeline (clean, chunk by paragraph ~300-500 tokens,
attach metadata, embed, upsert idempotently to Qdrant), the retriever with optional tag filter, the
search_tactical_knowledge tool, the RAG node wired after Player/Tactical for tactical/comparison queries, and the
Sources section in the report. Check current Qdrant client docs and propose an embedding model with reasoning
before implementing. Treat retrieved text as untrusted data in prompts. Build the retrieval test set first.
```

**Commit:** `feat(phase-7): rag knowledge base and citations`
**Handoff notes:** _(fill in: embedding model, chunking params, hit-rate)_

---

## Phase 8 — Critic and refinement loop

**Goal:** enforce grounding automatically; bad reports don't reach the user.
**Depends on:** Phase 7. **Estimate:** ~2 weeks.

### Scope
1. **Two-layer critic** (`agents/critic.py`, `graph/nodes/critic.py`):
   - **Layer 1: deterministic checks** (code, no LLM), run first:
     a. every claim has non-empty `evidence_refs` that resolve to real state entries;
     b. numeric claims literally match values in `team_stats/player_stats/events` (tolerance for rounding);
     c. all named players/teams/formations exist in state;
     d. two findings that address the same fact don't disagree (structured comparison).
   - **Layer 2: separate LLM call** (never the same call as Synthesis) for reasoning validity: does the conclusion follow from the cited evidence?
   - Returns `CriticResult` (section 6.2).
2. **Conditional routing:** `passed` → Report; failed → route by `required_action` to *only* the relevant node (`retrieve_more_data` → data_retrieval; `redo_tactical`; `redo_player`), attaching the critic's issues as context. Increment `retry_count`; cap at `MAX_CRITIC_RETRIES` (default 2).
3. **After cap:** produce a report flagged **low confidence** listing unresolved issues; conflicting findings shown as "Unresolved disagreement" with both sides (never silently pick one). Evidence priority on conflicts: tool data > RAG > agent interpretation.
4. **Query routing:** lightweight critic (Layer 1 only) for `player`; full critic for `tactical`/`comparison`/`report`; skipped for `simple_stat`.
5. Persist `critic_feedback` and `retry_count` in `agent_runs`.
6. **Adversarial test set:** `tests/graph/adversarial/` — deliberately corrupted drafts (fake stat, nonexistent player, unsupported leap, contradiction) that the critic must catch.
7. Feature flag `ENABLE_CRITIC` to compare with/without in eval.

### Tests
- Layer 1 unit tests (no LLM): each check with pass/fail cases.
- Adversarial set: ≥ 90% of injected errors detected.
- Graph: loop never exceeds the cap (property/parametrized); retry routes to the correct node; final low-confidence path works; retry counter increments.
- Regression: golden set faithfulness/hallucination metrics improve vs Phase 7 (record numbers in handoff).

### Acceptance checks
- [ ] Injected fake numbers are caught and never appear in final output.
- [ ] Worst case is bounded: ≤ `MAX_CRITIC_RETRIES` + 1 passes through the loop.
- [ ] Low-confidence and unresolved-disagreement rendering works.
- [ ] Latency/cost increase measured and documented.

### AI prompt
```
Implement Phase 8 of IMPLEMENTATION.md. Build the deterministic Layer 1 critic checks first with unit tests, then the
separate LLM Layer 2 critic with a strict CriticResult schema, the conditional routing to only the node that needs
redoing, a retry counter with a hard cap, and the low-confidence/unresolved-disagreement report path. Build the
adversarial corrupted-draft test set BEFORE tuning prompts. Add the ENABLE_CRITIC flag and show me
eval numbers with and without the critic.
```

**Commit:** `feat(phase-8): critic agent and bounded refinement loop`
**Handoff notes:** _(fill in: detection rate, false-positive rate, latency delta)_

---

# RELEASE 4 — FULL PRODUCT

## Phase 9 — Frontend v2

**Goal:** the complete experience from the design doc's frontend section.
**Depends on:** Phase 8. **Estimate:** 2–3 weeks total. Split into sub-PRs (9a–9e), one AI session each: 9a ~3d, 9b ~4d, 9c ~3d, 9d ~5d, 9e ~4d. 9a freezes the SSE contract in section 6.6 before the UI consumes it.

### 9a — Streaming
- Backend: `POST /analysis/stream` using **Server-Sent Events**; events: `node_started`, `node_finished`, `token` (final answer chunks), `final` (full `AnalysisResult`), `error`. Sourced from LangGraph streaming.
- Frontend: chat shows live node status ("Fetching data → Analyzing tactics → Checking claims…"), streams the final answer, handles disconnects/aborts.
- Test: SSE contract test; FE test with a mocked stream.

### 9b — Match Overview and Dashboard
- Dashboard: match search, recent analyses (from `agent_runs`/`reports`), quick-start into analyst.
- Match Overview: score, possession, xG, shots, passes, PPDA, field tilt with bar + radar charts.

### 9c — Event Timeline
- Horizontal timeline of key events (goals, shots, cards, subs). Clicking an event pre-fills a question in the chat ("Explain what happened at 34' …").
- Needs `GET /matches/{id}/events?event_type=` filtering (exists) and pagination if large.

### 9d — Tactical and Player views
- Tactical: simple SVG pitch with formation overlay (from `formations`), possession-flow/shot map, findings list with evidence links and confidence badges.
- Player: player cards and sortable stat grid; select a player → `POST /analysis/player`.

### 9e — Report view and Comparison
- Report page (`/reports/:id`): rendered sections, inline citations to evidence and sources, confidence indicator, low-confidence/unresolved banners.
- Comparison: pick two matches → `POST /analysis/comparison` (+ `compare_matches` tool) → side-by-side diff and narrative.

### Acceptance checks (whole phase)
- [ ] Every screen listed in the design's frontend section exists and works with real data.
- [ ] Streaming works end to end; aborting a request stops server work (or at least the stream).
- [ ] Responsive at mobile widths; no console errors.
- [ ] Critical paths covered by component tests + one E2E smoke test per screen group.

### AI prompt (use once per sub-phase, swapping the letter)
```
Implement Phase 9<letter> of IMPLEMENTATION.md only. Reuse the existing API client and components. Confirm which
backend endpoints/contracts this sub-phase needs (adding them if missing, with tests), then build the UI with tests.
Do not start other sub-phases.
```

**Commit(s):** `feat(phase-9a): sse streaming` … `feat(phase-9e): report and comparison`
**Handoff notes:** _(fill in)_

---

# RELEASE 5 — PRODUCTION

## Phase 10 — Full evaluation

**Goal:** measure quality objectively so changes can be judged, not guessed.
**Depends on:** Phase 8 (Phase 9 recommended). **Estimate:** ~1.5 weeks.

### Scope
- Grow the golden set to **25–30 questions** across simple_stat / player / tactical / comparison, each with expected evidence.
- Metrics computed by `scripts/run_eval.py`:
  factual accuracy, tool accuracy (right tool, right args), retrieval relevance, answer faithfulness (claims supported by evidence), **hallucination rate**, latency (p50/p95), token usage/cost, task completion rate.
- LLM-as-judge only for faithfulness/tactical quality, with a fixed judge prompt and spot-checked against human labels on ≥ 10 samples.
- **Failure test matrix** (each must degrade gracefully, per the design): data-source failure, missing `player_id`, missing `match_id`, malformed query, LLM timeout, tool timeout, empty RAG results, contradictory agent findings.
- Output: a versioned report `eval_reports/YYYY-MM-DD.md` plus JSON; a comparison mode (this run vs previous).
- Write target thresholds in `docs/quality-bar.md` (e.g., hallucination rate < 2%, factual accuracy ≥ 90%). CI runs a small smoke subset; the full eval runs on demand/nightly.

### Acceptance checks
- [ ] One command produces the full metrics report.
- [ ] All failure-matrix tests pass.
- [ ] Baseline numbers recorded; thresholds documented.
- [ ] Judge agreement with human labels documented.

### AI prompt
```
Implement Phase 10 of IMPLEMENTATION.md. Expand the golden dataset to 25-30 questions with expected evidence, build
the eval harness computing every metric listed (with a spot-checked LLM judge only where needed), implement the full
failure-test matrix, add run-to-run comparison and a report generator, and document quality-bar thresholds. Do not
change agent behavior in this phase; only measure and report.
```

**Commit:** `feat(phase-10): evaluation harness and quality bar`
**Handoff notes:** _(fill in baseline numbers)_

---

## Phase 11 — Observability

**Goal:** see exactly what every run did, cost, and where it failed.
**Depends on:** Phase 10. **Estimate:** ~1 week.

### Scope
- LangSmith tracing across the graph (nodes, LLM calls, tool calls, retrieval, critic); tag runs with `agent_run_id`, `query_type`, `environment`. Redact secrets and any user PII in traces.
- **Postgres-backed checkpointer** so runs are inspectable/resumable; retention policy documented. Checkpoint snapshots go through the same sanitizer and size cap as Phase 5's state test (R9): no raw event payloads, no embeddings, no prompt history.
- Per-run token and cost accounting from the LLM wrapper into `agent_runs` (cost table configurable).
- Structured logs correlate `request_id` ↔ `agent_run_id` ↔ LangSmith trace ID.
- A simple internal admin view or SQL views: p95 latency, cost per query type, degraded rate, retry rate, critic fail rate (a `/admin/metrics` endpoint guarded by a token is enough).
- Use LangSmith datasets/evals if convenient, but the Phase 10 harness stays the source of truth.

### Acceptance checks
- [ ] Any run can be found in LangSmith from its `run_id` and shows the full node tree.
- [ ] A deliberately failing run is diagnosable from traces alone.
- [ ] Cost per query type is reportable.
- [ ] Tracing can be disabled via env without code changes.

### AI prompt
```
Implement Phase 11 of IMPLEMENTATION.md. Add LangSmith tracing with run tagging and redaction, the Postgres
checkpointer (check current LangGraph docs for the right saver), token/cost accounting in agent_runs, correlated
logging, and a token-protected /admin/metrics endpoint. Tracing must be toggleable by env vars. Add tests where
feasible (mock the tracer) and document how to debug a bad run.
```

**Commit:** `feat(phase-11): observability, checkpointing, cost tracking`
**Handoff notes:** _(fill in)_

---

## Phase 12 — Security and deployment

**Goal:** a safe, live, reproducible deployment.
**Depends on:** Phase 11. **Estimate:** ~2 weeks.

### 12a — Hardening
- **Auth:** simple JWT or session auth (or an auth provider) protecting `/analysis*` and `/admin/*`; `/health` and read-only match data can stay public if desired.
- **Rate limiting** per user/IP on `/analysis*`.
- **Cost controls:** per-user daily token budget; max query length; hard cap on graph steps and tool calls per run.
- **Caching:** cache deterministic tool results and identical analysis requests (key = normalized query + match + data/prompt version).
- **Prompt-injection defenses:** user text and retrieved text are always delimited as untrusted data; agents can't call tools outside the registry; tool args re-validated server-side; ingestion scripts sanitize/flag suspicious documents.
- **CORS** restricted to `CORS_ORIGINS`; security headers; dependency audit (`pip-audit`, `npm audit`).

### 12b — Deployment
Order matters:
1. **Postgres** on Neon or Supabase → set `DATABASE_URL`.
2. **Backend** on Render or Railway via Dockerfile; **migrations run as a deploy step**; `/health` used as the platform health check.
3. **Qdrant Cloud** collection created and seeded via `ingest_kb.py` (embedding model must match Phase 7).
4. **Frontend** on Vercel with `VITE_API_URL` pointing to the live backend.
5. Load seed data via the ETL/compute scripts against production DB (documented runbook).
- `docs/runbook.md`: deploy, rollback, rotate keys, re-ingest KB, restore DB.
- Post-deploy smoke test script hitting the live URL (health, list matches, one simple and one tactical analysis).

### Acceptance checks
- [ ] Unauthenticated calls to `/analysis` are rejected; rate limit and budget enforcement demonstrated.
- [ ] Prompt-injection test set (user text and KB doc) does not change agent behavior or leak the system prompt.
- [ ] Live URL passes the smoke test; migrations applied automatically.
- [ ] No secrets in the repo (run a secret scanner); keys only in platform env settings.
- [ ] README has the live URL, architecture diagram, and demo instructions. Tag `v1.0.0`.

### AI prompt (use for 12a, then 12b)
```
Implement Phase 12<a|b> of IMPLEMENTATION.md. For 12a: auth, rate limiting, token budgets, caching, prompt-injection
defenses with an adversarial test set, CORS/security headers. For 12b: production Dockerfile, deployment config for
Render/Railway, migration-on-deploy, Qdrant Cloud seeding, Vercel config, runbook, and a post-deploy smoke test
script. Check each platform's current docs and free-tier limits. Never place secrets in files.
```

**Commit:** `feat(phase-12a): security hardening` / `chore(phase-12b): production deployment`
**Handoff notes:** _(fill in URLs (not secrets), deploy gotchas)_

---

# RELEASE 6 — STRETCH (Phase 13)

Do these only after v1.0.0, ordered by evidence from eval and user feedback. Each is its own numbered mini-phase (13a–13h) with tests and an eval comparison.

| Mini-phase | Trigger to do it | Notes |
|---|---|---|
| 13a Live data adapter | You want current matches | Implement a new `MatchDataService`; agents/tools unchanged (R10). Check provider licensing and rate limits first. |
| 13b Reranking | Retrieval hit-rate < target or results topically close but off | Add after the retriever; re-measure hit-rate. |
| 13c Hybrid search (BM25 + vectors) | Keyword-heavy queries retrieve poorly | Qdrant supports it; compare in the RAG test set. |
| 13d Report export (PDF/share link) | Users want to share | Server-side render of the report template. |
| 13e User feedback (👍/👎 + comment) | You need real-world signal | Store per `run_id`; feed failures back into the golden set. |
| 13f More seasons/competitions | Coverage complaints | Re-run ETL/compute; re-run eval to check no regressions. |
| 13g Saved conversations / memory | Multi-turn usage | Design state carefully; keep R9. |
| 13h Model tiering | Cost too high | Cheaper model for analyzer/orchestrator/formatter; keep strong model for synthesis/critic; verify with eval. |

---

# Appendix A — Suggested DB schema (final)

```
teams(id PK, name, country, founded_year, source_id)
players(id PK, name, team_id FK, position, birth_date, source_id)
matches(id PK, home_team_id FK, away_team_id FK, competition, season, match_date, home_score, away_score, source_id)
events(id PK, match_id FK, minute, second, event_type, team_id FK, player_id FK NULL, x, y, outcome,
       xg NULL, related_event_id NULL, possession_id NULL, source_id)   INDEX(match_id, minute)
player_match_stats(id PK, match_id FK, player_id FK, minutes_played, goals, assists, xg, xa, passes,
                   pass_accuracy, shots, tackles, position_played)      UNIQUE(match_id, player_id)
team_match_stats(id PK, match_id FK, team_id FK, possession_pct, xg, shots, ppda, field_tilt, formation)
                                                                        UNIQUE(match_id, team_id)
formations(id PK, match_id FK, team_id FK, formation_string, period, start_minute)
agent_runs(id PK, created_at, user_query, query_type, graph_state_snapshot jsonb, status, retry_count,
           latency_ms, token_usage jsonb, cost_usd, error)              INDEX(created_at)
tactical_analysis(id PK, match_id FK, agent_run_id FK, category, summary, confidence)
reports(id PK, agent_run_id FK, match_id FK NULL, content, created_at)
```

Migrations: `0001` (Phase 1), `0002` agent_runs (Phase 5), `0003` tactical_analysis + reports (Phase 6).

# Appendix B — Query routing table

| Query type | Nodes |
|---|---|
| simple_stat | analyzer → orchestrator → data_retrieval → simple_formatter → END |
| player | … → data_retrieval → player_agent → critic (light) → report |
| tactical | … → data_retrieval → tactical_agent → rag → synthesis → critic → report |
| comparison | … → data_retrieval (both matches) → player + tactical (parallel, per match) → rag → synthesis (comparison prompt) → critic → report |

Every tool-calling node has an error edge to `degraded_response`. Critic failures loop only to the node named in `required_action`, capped by `MAX_CRITIC_RETRIES`.

# Appendix C — Golden eval record format

```json
{
  "id": "q007",
  "type": "tactical",
  "match_id": 12345,
  "question": "How did Team A press against Team B?",
  "expected_values": {"ppda_team_a": 7.4, "ppda_team_b": 12.1},
  "must_reference": ["team_match_stats"],
  "must_not_contain": ["invented player names"],
  "notes": "Expected: identifies high press; cites PPDA from tools"
}
```
Expected values are always computed from the database/metrics code, never from an LLM.

# Appendix D — Phase prompt template (for your own additions)

```
Context: I'm building the AI Football Match Analyst. I've attached IMPLEMENTATION.md sections 1-4 and 6, plus the
handoff notes from previous phases. Implement ONLY <Phase N: name>.
1. Restate the goal and scope in your own words.
2. List files to create/modify and wait for my approval.
3. Implement with tests alongside (no LLM in unit tests).
4. Verify library APIs against current official docs.
5. Run lint, type checks and tests; show me the output.
6. Give me the exact commands to run each acceptance check.
7. Draft the handoff notes (what was built, deviations, known issues).
Anything outside scope goes to BACKLOG.md.
```

# Appendix E — Common mistakes to avoid

- Letting the LLM see raw DB rows it doesn't need (bloats tokens, invites errors).
- Computing a metric two ways in two places — all metrics live in `app/analytics/`.
- Mixing embedding models in one Qdrant collection.
- Building the critic as the same call as synthesis (it will rubber-stamp itself).
- Unbounded loops: every loop has a counter and cap; every external call has a timeout.
- Skipping the golden set "until later" — regressions then go unnoticed.
- Changing shared contracts in section 6 without updating this file and the handoff notes.
