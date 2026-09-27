# AI Football Match Analyst

A web app where you pick a football match, see its stats, and ask questions in plain language.
A multi-agent system answers with a grounded analysis: **every number traces to a deterministic
tool call, and tactical claims cite sources.**

Built incrementally from [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) — one phase per session, with
acceptance checks run at the end of each phase.

**Current status: Phase 0 (Foundation).** The skeleton runs end to end: API, `/health`, lint/type/test
tooling, CI and the infrastructure containers. There is no match data or LLM yet.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 19 + Vite 8 + TypeScript + Tailwind 4 |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| DB / vector store | PostgreSQL 16 + Qdrant (docker compose) |
| Tooling | ruff + mypy (strict), pytest / ESLint + Prettier, Vitest |

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22+ (24 recommended) and npm
- Docker with Compose v2

## Quickstart

```bash
# 1. Infrastructure: Postgres 16 + Qdrant
docker compose up -d

# 2. Configuration (.env is gitignored; .env.example documents every key)
cp .env.example .env

# 3. Backend dependencies
cd backend && uv sync

# 4. Migrate the database and load the dataset (~87 MB the first time, then cached)
#    From the repository root:
uv run --project backend python scripts/seed.py

# 5. Run the API (http://localhost:8000)
#    On Windows, --loop is required: without --reload uvicorn serves on a Proactor
#    event loop, which psycopg's async driver refuses. (With --reload the flag is
#    unnecessary but harmless.) No-op on Linux/macOS.
cd backend && uv run uvicorn app.main:app --loop app.core.eventloop:psycopg_safe_uvicorn_loop_factory --reload

# 6. In a second terminal: the frontend (http://localhost:5173)
cd frontend && npm install && npm run dev

# 7. Open http://localhost:5173 — the page should read "API healthy"
```

Compose publishes Postgres on **host port 55432** (the container still listens on 5432). Plain 5432
is avoided because a native Postgres install usually already owns it, and Windows reserves whole
port ranges (5433-5532 by default) where nothing can bind. `DATABASE_URL` in `.env.example` matches.

With Postgres up, `GET /health` reports `{"status": "ok", "db": "ok"}`. With it down (or
`DATABASE_URL` unset) the API still returns 200 but reports `degraded` / `unavailable` — failures
degrade, they don't crash.

## Common commands

**Backend** (from `backend/`):

```bash
uv run pytest            # tests (LLM-marked tests are deselected by default)
uv run pytest -m llm     # tests that call a real LLM: needs GROQ_API_KEY
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy app          # strict type check
```

**Frontend** (from `frontend/`):

```bash
npm test                 # Vitest
npm run lint             # ESLint
npm run format           # Prettier
npm run build            # tsc -b + production build
```

## Project layout

```
backend/app/{api,agents,graph,tools,analytics,rag,models,schemas,services,core}
backend/tests/{unit,api,agents,graph,rag,eval}
frontend/src/{api,components,test}
docs/ scripts/ data/ knowledge_base/
```

`app/core/` holds configuration, structured JSON logging, the error hierarchy and the database
engine. Only `api/` and `core/` are populated in Phase 0; the other packages land in the phases that
own them (`analytics/` Phase 2, `tools/` + `agents/` Phase 3, `graph/` Phase 5, `rag/` Phase 7).

## Conventions

- Python: type hints everywhere, `mypy --strict` on `app/`, no business logic in routers.
- Errors: raise the `AppError` hierarchy from `app/core/errors.py`; the app maps it to HTTP
  (404/422/502/504) and returns `{"error": {code, message, context?, request_id?}}`.
- Tests: `tests/unit` needs no network and no LLM. Agent/LLM tests are marked `@pytest.mark.llm`.
- Config: one `Settings` object in `app/core/config.py`; never read `os.environ` directly.
- Commits: Conventional Commits, one commit per phase (`feat(phase-0): project foundation`).

## Toolchain notes

- **TypeScript is pinned to ~6.0.3.** `typescript-eslint` 8.x declares `typescript: <6.1.0`, so
  TypeScript 7 (current latest) would break linting. Revisit when typescript-eslint supports it.
- **Vitest uses `pool: 'threads'`** — the default `forks` pool intermittently times out starting
  workers on Windows.
- GitHub Actions are pinned to commit SHAs (with the version in a comment), because
  `astral-sh/setup-uv` no longer publishes mutable major tags.

## Workflow

Phases, acceptance checks and handoff notes live in [`IMPLEMENTATION.md`](./IMPLEMENTATION.md);
[`PHASES.md`](./PHASES.md) is the one-page map of all of them. Anything out of scope for the current
phase goes to [`BACKLOG.md`](./BACKLOG.md) instead of the code.
