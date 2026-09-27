# AI Football Match Analyst — Architecture & Roadmap

A production-style, learning-first blueprint for a multi-agent football tactical analysis system. This page covers architecture, agents, LangGraph design, state, tools, RAG, database, API, frontend, folder structure, phased roadmap, testing/evaluation, deployment, and interview prep.

**No code yet — this is the design.** Implementation happens milestone by milestone, in follow-up conversations.

---

# 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│ React + Vite Frontend (Dashboard, Chat, Reports)         │
└───────────────────────┬───────────────────────────────────┘
                         │ REST (JSON)
┌───────────────────────▼───────────────────────────────────┐
│ FastAPI Backend                                            │
│  - Request validation (Pydantic)                           │
│  - Auth, rate limiting                                     │
│  - Invokes LangGraph runner, streams results                │
└───────────────────────┬───────────────────────────────────┘
                         │
┌───────────────────────▼───────────────────────────────────┐
│ LangGraph Orchestration Layer (stateful graph)              │
│  Question Analyzer → Orchestrator → parallel agent branches │
│  → RAG → Synthesis → Critic → (retry loop) → Report          │
└───────────────────────┬───────────────────────────────────┘
                         │
        ┌────────────────┼───────────────────┐
        ▼                ▼                    ▼
┌───────────────┐ ┌──────────────┐   ┌─────────────────┐
│ Specialized     │ │ Tool Layer   │   │ RAG Retriever    │
│ Agents (LLM +   │ │ (deterministic│   │ (Qdrant vector   │
│ prompts)        │ │ Python funcs) │   │ store)           │
└───────┬────────┘ └──────┬───────┘   └────────┬─────────┘
        │                  │                     │
        ▼                  ▼                     ▼
┌────────────────────────────────────┐  ┌──────────────────┐
│ PostgreSQL (matches, events,        │  │ Knowledge base     │
│ players, stats — source of truth)   │  │ docs (tactics)      │
└────────────────────────────────────┘  └──────────────────┘
```

**Why this shape, and one change from your draft:** the original diagram put agents *below* tools, implying agents call tools directly and nothing else. In practice the LangGraph orchestration layer sits *between* the API and everything else — it's the thing that decides which agents run, in what order, and whether to loop. Agents themselves are just LLM calls with prompts + tool access; they don't "own" the tools, the graph wires tools into each agent node. So the real ownership chain is: **API → Graph → (Agent nodes that call Tools/RAG) → Postgres/Vector DB**, not a strict top-to-bottom pipeline.

**Why each layer exists**

- **Frontend**: presentation only. No business logic, no LLM calls.
- **FastAPI**: thin transport layer — validates input, calls the graph, formats output.
- **LangGraph**: the actual "brain" that decides *what happens next*. This is what makes it agentic rather than a chatbot with a system prompt.
- **Agents**: narrow, single-responsibility LLM reasoning units.
- **Tools**: deterministic, testable functions agents call for facts. This is the anti-hallucination backbone.
- **Postgres**: ground truth for structured match data.
- **Vector DB**: unstructured tactical knowledge that doesn't fit a relational schema.

---

# 2. Tech Stack (recommended)

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | React + Vite + Tailwind + Recharts | Fast dev loop, good chart ecosystem |
| Backend | FastAPI | Async, Pydantic-native, great for LLM streaming |
| Orchestration | LangGraph | Explicit state machine, branching, loops, retries |
| LLM | Grok via xAI API | Strong tool-use + structured output support |
| Structured I/O | Pydantic v2 | Validates every agent/tool boundary |
| Relational DB | PostgreSQL | Mature, relational integrity for match data |
| ORM/migrations | SQLAlchemy + Alembic | Standard, testable, migration history |
| Vector DB | Qdrant | Good filtering support, easy local + cloud story |
| Embeddings | Any strong general-purpose embedding model (evaluate current options when you get there) | — |
| Observability | LangSmith | Purpose-built for LangChain/LangGraph traces |
| Testing | pytest + pytest-asyncio | Standard Python stack |
| Deployment | Vercel (FE) / Render or Railway (BE) / Neon or Supabase (Postgres) / Qdrant Cloud | Free/cheap tiers, low ops overhead |

---

# 3. Agent Architecture

Your proposed 8 agents are mostly right-sized. One adjustment: **merge "Match Data Agent" into being mostly tool-calls with a thin LLM wrapper**, because most of its job (fetching stats) needs zero reasoning. Keep it as an agent only for the parts that need light interpretation (e.g., picking *which* stats matter for a query).

| Agent | Responsibility | Needs LLM reasoning? |
| --- | --- | --- |
| **Orchestrator** | Classify query type, decide which agents/tools to invoke, set the execution plan | Yes — light |
| **Match Data Agent** | Fetch/format factual stats & events via tools | Mostly no — thin LLM layer for query-shaping only |
| **Player Analysis Agent** | Interpret player stats into a performance narrative | Yes |
| **Tactical Analysis Agent** | Reason over formations/pressing/possession/transitions | Yes — the core "analyst" |
| **RAG Agent** | Retrieve tactical knowledge relevant to the question/findings | Mostly no — retrieval is deterministic; LLM only for query reformulation |
| **Synthesis Agent** | Merge Data + Player + Tactical + RAG findings into one coherent draft | Yes |
| **Critic Agent** | Validate claims against evidence, flag hallucination/contradictions | Yes — but with structured, rule-driven output |
| **Report Generation Agent** | Turn the validated synthesis into a polished user-facing report | Yes — mostly formatting/tone |

**Do not add:** a separate "Formation Agent" or "Possession Agent" etc. — that's over-decomposition. Tactical sub-domains are *prompts/sections within* the Tactical Analysis Agent, not separate agents, until you have concrete evidence one needs independent tool access or independent retry logic.

---

# 4. LangGraph Design

```
START
  │
  ▼
Question Analyzer  ── classifies query type, extracts match_id/team_ids/player_ids
  │
  ▼
Orchestrator  ── builds an execution plan (which branches to run)
  │
  ▼
Data Retrieval (Match Data Agent + tools)  ── always runs; grounds everything downstream
  │
  ├──────────────┬───────────────┐
  ▼              ▼               │ (conditional — skipped if not needed)
Player Agent   Tactical Agent    │
  │              │               │
  └──────┬───────┘               │
         ▼                       │
     RAG Agent  ◄─────────────────┘ (only for tactical/complex queries)
         │
         ▼
  Synthesis Agent
         │
         ▼
  Critic Agent
         │
   ┌─────┴─────┐
   ▼           ▼
 FAILED       PASSED
   │           │
   ▼           ▼
Refinement   Report Agent
   │             │
   └──►(loop back to Critic, max N retries)
                 ▼
                END
```

**Improvements over the draft:**

- **Conditional edges everywhere**, not just at the critic. Simple stat queries should skip Player/Tactical/RAG entirely and go straight from Data Retrieval → a lightweight formatter → END.
- **Max retry counter in state.** Without it, Critic→Refinement→Critic can loop forever. Cap at e.g. 2 retries, then return a "low confidence" report rather than looping indefinitely.
- **Refinement doesn't always mean "run everything again."** The Critic's structured output should say *what* is missing, and the refinement edge routes back to only the relevant node, not the whole graph.
- **A fallback/error edge** from every tool-calling node straight to a "degraded response" path, so a single API failure doesn't crash the whole graph.

**Why LangGraph over a sequential LangChain chain:** a chain executes a fixed sequence — no branching on query type, no parallel agent execution, no conditional retry loop, and no persisted, inspectable state between steps. Your system needs all four: different query types need different agent subsets (branching), Player + Tactical can run concurrently (parallelism), the Critic needs to be able to send work backward (cycles — chains are DAGs/linear, LangGraph explicitly supports cycles), and you need a single state object you can log, checkpoint, and resume (observability + reliability). This is the single most defensible "why LangGraph" answer for an interview.

---

# 5. State Design

```python
from typing import TypedDict, Literal, Optional
from pydantic import BaseModel

class CriticIssue(BaseModel):
    type: Literal["unsupported_claim", "contradiction", "hallucination", "missing_evidence"]
    claim: str
    reason: str

class CriticResult(BaseModel):
    passed: bool
    issues: list[CriticIssue]
    required_action: Optional[Literal["retrieve_more_data", "redo_tactical", "redo_player", "none"]]

class AgentFinding(BaseModel):
    agent: str
    summary: str
    evidence_refs: list[str]   # pointers into match_data/events/retrieved_documents, not raw duplication
    confidence: float

class GraphState(TypedDict):
    # input
    user_query: str
    query_type: Literal["simple_stat", "player", "tactical", "comparison", "report"]
    match_id: Optional[int]
    team_ids: list[int]
    player_ids: list[int]

    # retrieved facts (populated once, reused — not re-fetched per agent)
    match_data: Optional[dict]
    team_stats: Optional[dict]
    player_stats: Optional[dict]
    events: Optional[list[dict]]

    # RAG
    retrieved_documents: list[dict]   # [{content, source, score}]

    # agent outputs — findings, not raw data
    agent_findings: list[AgentFinding]

    # critic loop
    critic_feedback: Optional[CriticResult]
    retry_count: int

    # output
    final_report: Optional[str]
```

**What belongs in state:** identifiers (match_id, team_ids), retrieved facts that multiple nodes need, agent *findings* (summaries + evidence pointers), critic feedback, retry counters, final output.

**What should NOT be in state:** full prompt/completion text history, raw large event payloads once a summarized finding exists, embeddings themselves, anything that isn't needed by a later node.

**Keeping state small / token-aware:** store *references* to evidence (e.g., `event_id: 431`) rather than copying full event text into every agent's context; only expand references when actually building the final prompt; truncate `retrieved_documents` to top-k with scores; findings should be short structured summaries, not raw LLM transcripts.

**Persistence later:** LangGraph supports checkpointing state to a store (e.g., Postgres-backed checkpointer) so a run can be paused/resumed and you get replayability for debugging — worth adding once the graph is stable, not on day one.

---

# 6. Tool System

All tools are deterministic Python functions with explicit Pydantic input/output schemas — the LLM never writes SQL or free-form queries.

| Tool | Input | Output | Used by | Deterministic |
| --- | --- | --- | --- | --- |
| `get_match_stats(match_id)` | int | team/match summary stats | Match Data Agent | Yes |
| `get_match_events(match_id, event_type?)` | int, optional filter | list of events | Match Data, Tactical | Yes |
| `get_player_stats(player_id, match_id?)` | int(s) | player stat dict | Player Agent | Yes |
| `get_team_stats(team_id, match_id?)` | int(s) | team stat dict | Match Data, Tactical | Yes |
| `get_shot_data(match_id)` | int | shot list w/ xG, location | Tactical, Player | Yes |
| `get_possession_sequences(match_id)` | int | possession chains | Tactical | Yes |
| `search_tactical_knowledge(query, top_k)` | str, int | ranked doc chunks + source | RAG Agent | Retrieval yes; query reformulation may use LLM |
| `calculate_player_metric(player_id, metric)` | int, enum | computed number | Player Agent | Yes |
| `compare_matches(match_id_a, match_id_b)` | int, int | diffed stats | Synthesis (comparison queries) | Yes |

Each tool: validates inputs, returns typed output (Pydantic model, not a raw string), raises a specific exception type on failure (`MatchNotFoundError`, `DataUnavailableError`) that the graph can catch and route to a fallback node, and is unit-testable in isolation with no LLM involved. This is what makes "don't let the LLM invent stats" actually enforceable — the LLM only ever *sees* tool outputs, it never generates numbers itself.

---

# 7. Data Source Strategy

*(Research this live once you reach Phase 1 — API landscapes and free tiers shift. Framework to evaluate against:)*

- **Free/open**: look for open event-data projects (e.g., community-maintained StatsBomb open data, [football-data.org](http://football-data.org) free tier) — good for prototyping with real match/event structure, but limited match coverage and no live data.
- **Freemium**: APIs offering a free tier with basic fixtures/stats and paid tiers for event-level/xG data — good middle ground for a portfolio project; check current rate limits before committing.
- **Paid**: professional providers (Opta-style) with full event streams — almost certainly out of budget/licensing reach for a student project; mention in your writeup as "the production-grade option" without integrating it.

**Recommendation for this project:** start with an open, static dataset (season(s) of match + event data) loaded into Postgres once via an ETL script, rather than a live API. This removes rate-limit/auth complexity from the *agentic AI* learning goal, which is the actual point of the project. Add a live API adapter later as a stretch goal if time permits — design the `MatchDataService` interface so the source is swappable without touching agents/tools.

When you're ready to pick specific providers, ask and I'll web-search current options, licensing terms, and rate limits rather than relying on memory.

---

# 8. Database Schema (PostgreSQL)

```
teams
  id PK, name, country, founded_year

players
  id PK, name, team_id FK→teams, position, birth_date

matches
  id PK, home_team_id FK→teams, away_team_id FK→teams,
  competition, match_date, home_score, away_score, season

events
  id PK, match_id FK→matches, minute, second, event_type,
  team_id FK→teams, player_id FK→players (nullable),
  x, y, outcome, related_event_id (nullable, for e.g. pass→shot chains)
  INDEX (match_id, minute)

player_match_stats
  id PK, match_id FK→matches, player_id FK→players,
  minutes_played, goals, assists, xg, xa, passes, pass_accuracy,
  shots, tackles, position_played
  UNIQUE (match_id, player_id)

team_match_stats
  id PK, match_id FK→matches, team_id FK→teams,
  possession_pct, xg, shots, ppda, field_tilt, formation
  UNIQUE (match_id, team_id)

formations
  id PK, match_id FK→matches, team_id FK→teams,
  formation_string, period ('full'|'first_half'|'second_half'), start_minute

tactical_analysis
  id PK, match_id FK→matches, agent_run_id FK→agent_runs,
  category, summary, confidence

agent_runs
  id PK, created_at, user_query, query_type, graph_state_snapshot (jsonb),
  status, retry_count, latency_ms, token_usage

reports
  id PK, agent_run_id FK→agent_runs, match_id FK→matches,
  content (text/markdown), created_at
```

Indexes worth calling out: `events(match_id, minute)` for timeline queries; `player_match_stats(match_id, player_id)` unique index doubles as a lookup index; `agent_runs(created_at)` for observability dashboards. Foreign keys everywhere to `matches`/`teams`/`players` keep referential integrity.

---

# 9. RAG Architecture

1. **Ingestion**: curate tactical concept documents (pressing, build-up structures, half-spaces, etc.) — start with a small, hand-picked set (10-20 solid articles/notes) rather than a huge scrape.
2. **Cleaning**: strip boilerplate/navigation, normalize headings.
3. **Chunking**: semantic/paragraph-based chunks (~300-500 tokens), not fixed character windows.
4. **Metadata**: `{source, title, concept_tags: ["pressing","half-space"], url}` per chunk — this is what makes citation possible later.
5. **Embeddings**: embed each chunk once at ingestion time, store vector + metadata in Qdrant.
6. **Vector DB**: Qdrant — supports metadata filtering, which plain cosine-only stores don't do as cleanly.
7. **Retrieval**: top-k (start with k=4-6) similarity search, optionally filtered by concept tags extracted from the query.
8. **Reranking**: add later if top-k results are topically close but not actually the most relevant — not needed for MVP with a small, curated corpus.
9. **Context construction**: only pass the retrieved chunk text + source into the RAG Agent/Synthesis prompt, not the whole document.
10. **Citation tracking**: every retrieved chunk keeps its `source` through to the final report.

---

# 10. Hallucination Reduction — the concrete mechanism chain

These aren't independent bullet points — they form a pipeline:

1. **Tool-grounded statistics**: every number in a report must trace back to a tool call output, never to free LLM generation.
2. **Structured outputs**: agents return Pydantic-validated JSON (finding + evidence_refs + confidence), not free text.
3. **Evidence requirement**: the Synthesis Agent's prompt requires every claim to carry an `evidence_ref`; claims without one are dropped before reaching the Critic.
4. **Source attribution**: RAG-derived tactical claims carry their source metadata through to the report.
5. **Critic agent**: cross-checks each claim in the draft against `match_data`/`events`/`retrieved_documents` actually present in state.
6. **Claim verification**: for numeric claims, the Critic can do a literal value match against `player_stats`/`team_stats`.
7. **Confidence estimation**: each agent finding carries a confidence score; low-confidence findings are excluded or flagged.
8. **Schema validation**: every agent/tool boundary is Pydantic-validated; malformed output fails fast.
9. **Retry/refinement**: Critic failures route back to the specific agent that needs to redo work, bounded by `retry_count`.
10. **Facts vs. interpretation separation**: the report template structurally separates a "What happened" section (tool-grounded facts only) from an "Analysis" section (tactical interpretation, explicitly labeled as reasoning, not fact).

---

# 11. Critic Agent Design

```python
class CriticIssue(BaseModel):
    type: Literal["unsupported_claim", "contradiction", "hallucination", "missing_evidence"]
    claim: str
    reason: str

class CriticResult(BaseModel):
    passed: bool
    issues: list[CriticIssue]
    required_action: Literal["retrieve_more_data", "redo_tactical", "redo_player", "none"]
```

Checks it runs, in order: (1) **factual correctness** — spot-check numeric claims against state; (2) **evidence grounding** — every claim has a non-empty `evidence_refs`; (3) **tactical reasoning validity** — does the stated conclusion follow from the cited evidence, or is it a leap (needs the LLM — it's judgment, not lookup); (4) **hallucination** — any player/event/formation named that doesn't exist in state; (5) **contradiction** — do two agent findings disagree on the same fact. The Critic should be a *separate* LLM call from Synthesis so it isn't just rubber-stamping its own reasoning.

---

# 12. Agent Disagreement Handling

- **Evidence weighting**: tool-grounded stats > RAG-retrieved general knowledge > agent interpretation, in that priority order when two findings conflict on a factual point.
- **Source priority**: structured DB data always wins over LLM-generated interpretation on factual questions.
- **Conflict detection**: the Critic explicitly diffs findings for the same claim from different agents and flags it, rather than the Synthesis Agent silently picking one.
- **Re-analysis**: on detected conflict, route back to whichever agent's claim isn't evidence-backed, with the conflicting finding attached as context.
- **Human review**: for genuinely unresolved conflicts after max retries, the report should surface *both* findings labeled as "unresolved disagreement" rather than the system picking arbitrarily.

---

# 13. Query Routing

| Query type | Nodes invoked |
| --- | --- |
| Simple stat ("How many shots?") | Data Retrieval → direct formatter → END (skip Player/Tactical/RAG/Critic entirely) |
| Player analysis | Data Retrieval → Player Agent → Critic (lightweight) → Report |
| Tactical question | Data Retrieval → Tactical Agent → RAG Agent → Synthesis → Critic → Report |
| Complex/comparison | Data Retrieval (both matches) → Player + Tactical (parallel, per match) → RAG → Synthesis (comparison-aware prompt) → Critic → Report |

The **Orchestrator** node is where this classification happens — it outputs a `query_type` and an explicit list of nodes to run, which conditional edges read to decide branching.

---

# 14. Frontend Architecture

- **Dashboard**: match list/search, recent analyses, quick-start into AI Analyst.
- **Match Overview**: score, possession, xG, shots, passes, PPDA, field tilt — Recharts bar/radar for team comparison.
- **Tactical Analysis**: formation diagrams (simple SVG pitch overlays are enough), possession flow, key findings list with evidence links.
- **Player Analysis**: player cards + stat grid, sortable.
- **Event Timeline**: horizontal timeline component; clicking an event fires a pre-filled question into the AI Analyst chat.
- **AI Analyst**: chat UI streaming the graph's final answer (and optionally intermediate node status).
- **Final Report**: rendered markdown/structured report with inline evidence citations and confidence indicators.

State management: React Query for server state + local component state for UI. No need for a heavy global store for a project this size.

---

# 15. API Design (FastAPI)

```
GET  /matches                          → MatchSummary[]
GET  /matches/{id}                     → MatchDetail
GET  /matches/{id}/stats               → TeamMatchStats[]
GET  /matches/{id}/events              → Event[]
GET  /matches/{id}/players             → PlayerMatchStats[]

POST /analysis                         → { query, match_id } → AnalysisResult (routes internally by query_type)
POST /analysis/tactical                → { match_id, focus? } → TacticalAnalysisResult
POST /analysis/player                  → { match_id, player_id } → PlayerAnalysisResult
POST /analysis/comparison              → { match_id_a, match_id_b } → ComparisonResult

GET  /reports/{id}                     → Report
```

`POST /analysis` is the general-purpose entry point the chat UI hits; the more specific endpoints exist for direct frontend widgets that don't need free-text query parsing. Every response body is a Pydantic model mirrored on the frontend via generated TS types.

---

# 16. Folder Structure

```
football-ai-analyst/
├── frontend/
│   └── src/{components,pages,hooks,api}/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── agents/         # one file per agent, prompt + logic
│   │   ├── graph/           # LangGraph definition, state, edges
│   │   ├── tools/           # deterministic tool functions
│   │   ├── rag/              # ingestion, retrieval, Qdrant client
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response/state schemas
│   │   ├── services/         # business logic bridging DB ↔ tools
│   │   └── core/             # config, logging, DB session, security
│   ├── tests/
│   │   ├── unit/ agents/ graph/ rag/
│   └── requirements.txt
├── data/                # raw/staged football datasets
├── knowledge_base/      # tactical docs for RAG ingestion
├── scripts/             # ETL, ingestion, seed scripts
├── docker-compose.yml   # postgres + qdrant for local dev
├── .env.example
└── README.md
```

---

# 17. Implementation Roadmap (Phases)

Each phase below: **Goal → Concepts → Key files → Tests → Definition of done → Difficulty → MVP or advanced.** Full milestone-level breakdown (with common mistakes + interview questions per milestone) should happen phase-by-phase as you actually reach them.

| Phase | Goal | Difficulty | MVP/Advanced |
| --- | --- | --- | --- |
| 0 — Project setup | Repo, env, Docker (Postgres+Qdrant), FastAPI skeleton returning a health check | Easy | MVP |
| 1 — Football data pipeline | Pick data source, ETL script loading matches/events/stats into staging | Medium | MVP |
| 2 — Database | Finalize schema, Alembic migrations, seed real match data | Medium | MVP |
| 3 — Basic analytics | Pure-Python functions computing PPDA/field tilt/etc. from raw events (no LLM yet) | Medium | MVP |
| 4 — LLM integration | First single LLM call: "summarize this match's stats" with structured output | Easy–Medium | MVP |
| 5 — Tool calling | Wrap Phase 1-3 functions as LLM tools; one agent calls one tool | Medium | MVP |
| 6 — LangGraph | Build the graph skeleton: Question Analyzer → Orchestrator → Data Retrieval → END | Medium–Hard | MVP |
| 7 — RAG | Ingest tactical docs, Qdrant retrieval, wire RAG Agent into graph | Medium–Hard | MVP |
| 8 — Multi-agent | Add Player + Tactical + Synthesis agents, parallel branches | Hard | MVP |
| 9 — Critic/reflection | Structured critic output, retry loop, retry cap | Hard | Advanced |
| 10 — Frontend | Dashboard, Match Overview, AI Analyst chat, Report view | Medium | MVP |
| 11 — Evaluation | Eval dataset + metrics (accuracy, groundedness, hallucination rate) | Hard | Advanced |
| 12 — Observability | LangSmith tracing across the whole graph | Medium | Advanced |
| 13 — Deployment | FE→Vercel, BE→Render/Railway, DB→Neon, Qdrant Cloud | Medium | Advanced |

**MVP cutline:** Phases 0-8 + 10 is a legitimately impressive, demo-able, interview-ready project on their own. Phases 9, 11, 12, 13 are what elevate it from "good project" to "this person understands production agentic AI" — do them if time allows.

**What to learn before each phase:**

- Before 0-3: basic FastAPI, SQLAlchemy, Pydantic, Docker Compose basics.
- Before 4-5: Grok/xAI tool-use API, Pydantic structured outputs.
- Before 6: LangGraph core concepts (nodes, edges, state, conditional routing).
- Before 7: embeddings basics, Qdrant client API, chunking strategies.
- Before 8-9: multi-agent patterns, reflection/critic patterns.
- Before 11-12: eval framework of your choice.

---

# 18. Testing Strategy

- **Unit**: tools, parsers, metric calculations — no LLM, fast, run on every commit.
- **Agent**: mock tool outputs, assert schema-valid `AgentFinding`; a small set of real LLM calls to sanity-check prompt quality.
- **Graph**: given a state, assert the correct next node is chosen for each `query_type`; assert retry_count increments and caps correctly.
- **RAG**: given known queries, assert expected documents appear in top-k.
- **Evaluation**: run the eval dataset end-to-end periodically, not on every commit.
- **Failure tests**: simulate data-source API failure, missing player_id, missing match_id, malformed query, LLM timeout, tool timeout, empty RAG results, and two agents returning contradictory findings — assert the graph degrades gracefully rather than crashing, for every one of these.

---

# 19. Agent Evaluation

Eval dataset: 20-30 hand-written questions spanning simple stat, player, tactical, and comparison types, each with a hand-written "expected evidence" reference.

Metrics: **factual accuracy**, **tool accuracy**, **retrieval relevance**, **answer faithfulness**, **hallucination rate**, **latency**, **token usage/cost**, **task completion rate**. A lightweight custom eval harness is enough for a project this size, though LangSmith's evaluation features are worth trying once you're at Phase 11-12.

---

# 20. Observability

LangSmith traces give you: query → graph execution → per-node agent calls → tool calls/results → RAG retrieval → critic → final answer, each with latency, token usage, and the actual prompts/completions. Without per-node tracing you're debugging blind; with it, you can pinpoint exactly which node in a multi-node run produced the bad output.

---

# 21. Production Concerns — MVP vs later

**Essential even for MVP:** input validation, basic error handling, structured logging, secret management (`.env`, never commit keys), retry-with-cap on the critic loop, database connection pooling, timeouts on all external calls.

**Add once the core works:** authentication/authorization, rate limiting, caching, prompt injection protection, malicious document handling in ingestion, cost controls/token budgets, CORS config for deployed frontend.

---

# 22. Deployment

```
Frontend  → Vercel
Backend   → Render or Railway
Postgres  → Neon or Supabase
Vector DB → Qdrant Cloud (free tier)
LLM       → Grok (xAI API)
Observability → LangSmith
```

Needed: `.env` with `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `GROK_API_KEY`, `LANGCHAIN_API_KEY` (LangSmith), `CORS_ORIGINS`; `docker-compose.yml` for local Postgres+Qdrant only; Alembic migrations run as a deploy step, not manually; a `/health` endpoint checked by the platform; deployment order: DB → backend (migrations run first) → Qdrant collection created/seeded → frontend pointed at the live backend URL.

---

# Next Step

Pick where you want to start — most people begin at **Phase 0** (project setup) or **Phase 1** (data pipeline), since everything downstream needs real match data to test against. Say which, and we'll go milestone by milestone: objective → concepts → files → smallest implementation → tests → definition of done → common mistakes → interview questions, one at a time, before moving on.