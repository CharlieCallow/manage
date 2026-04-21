# CLAUDE.md

Project orientation for Claude Code. Read this first, every session. Keep it in sync with reality as the code changes — if something here is no longer true, update this file before you write the code.

## 1. What this is

A local-first desktop app where the user plays PM of an AI-powered hedge fund. A team of Claude-backed agents (investor personas, analysts, risk, PM) produces research, debates theses, and backtests decisions. The user moves between rooms — Office, Research Desk, Committee Room, Trading Floor, Roster, Archive, Time Machine — that are different views over one underlying fund state.

Inspirations: multica-ai/multica (native desktop shell, ACP-style session orchestration) and virattt/ai-hedge-fund (persona + analyst + risk + PM graph).

This is an analytical / educational tool. It does not execute trades. See §14.

## 2. Current phase

**Phase 1 — Research Desk (slice).** Update this line on every phase boundary.

Phase 1 is done when: the Research Desk can take a ticker + one of three personas (Buffett, Druckenmiller, Burry), fan out to two analysts (valuation, fundamentals) in parallel, and produce a readable NVDA memo artifact — all driven through the job queue, with per-agent streaming visible in the UI.

Do not start Phase 2 work until Phase 1 runs end-to-end on a clean machine.

## 3. Repo layout

```
.
├── CLAUDE.md                  ← this file
├── README.md
├── apps/
│   ├── desktop/               Electron + React + TypeScript
│   │   ├── src/main/          Electron main process
│   │   ├── src/preload/       contextBridge
│   │   └── src/renderer/      React app (rooms, components, state)
│   └── backend/               FastAPI + LangGraph + Anthropic SDK
│       ├── app/api/           HTTP + WebSocket routes
│       ├── app/agents/        Persona + analyst graphs
│       ├── app/tools/         Agent tools (prices, filings, news)
│       ├── app/store/         SQLite access layer
│       └── app/schemas/       Pydantic models
├── packages/
│   └── shared-types/          TS types mirrored from Pydantic
├── data/
│   └── fund.sqlite            Local state; gitignored
└── .env.example
```

Never commit `data/fund.sqlite`, `.env`, or anything under `apps/backend/logs/`.

## 4. Tech stack (authoritative — don't switch without asking)

- **Desktop:** Electron + React 18 + TypeScript + Vite. Tailwind for styling. Zustand for renderer state. electron-builder for packaging.
- **Backend:** Python 3.11+, FastAPI, Uvicorn, LangGraph, Anthropic Python SDK (`anthropic`), Pydantic v2.
- **Storage:** SQLite via `sqlite3` / SQLAlchemy Core. No ORM layer beyond that. Migrations in `apps/backend/migrations/` run at startup.
- **Transport:** REST for CRUD, WebSocket (`/ws/jobs/{job_id}`) for streaming agent output.
- **Market data:** financial-datasets.ai (API key in `.env`) with a yfinance fallback for free tickers. Abstract behind `app/tools/market_data.py` — never call either directly from an agent.

## 5. Data model

All tables live in `fund.sqlite`. Schema in `apps/backend/migrations/001_init.sql`.

- `personas` — id, name, prompt_template, model, enabled, config_json, created_at
- `analysts` — same shape as personas. Seeded: valuation, sentiment, fundamentals, technicals, risk, pm
- `jobs` — id, type (research|committee|backtest), inputs_json, status, cost_usd, started_at, finished_at, error
- `artifacts` — id, job_id, kind (memo|transcript|signal|dcf|backtest_report), content_md, content_json, created_at
- `portfolio` — id, ticker, qty, avg_price, updated_at
- `portfolio_history` — id, ts, snapshot_json
- `persona_performance` — id, persona_id, period, trades, hit_rate, avg_return
- `sessions` — Multica-style chat threads. id, title, created_at + messages(session_id, role, content_md, ts)

A **job** is the unit of work. Anything an agent does happens inside a job. Artifacts are always attached to a job.

## 6. Agent contract

Every agent lives in `apps/backend/app/agents/` and implements:

```python
class Agent(Protocol):
    name: str
    model: str  # see §8

    async def run(self, job: Job, ctx: AgentContext) -> AsyncIterator[AgentEvent]:
        ...
```

`AgentEvent` is one of:

- `TokenEvent(text: str)` — streamed model output
- `ToolCallEvent(name, input)` / `ToolResultEvent(name, output)`
- `ArtifactEvent(artifact: Artifact)` — final deliverable
- `StatusEvent(status: str)` — "thinking" / "waiting_for_data" / "done"

The orchestrator (LangGraph) composes agents into graphs per job type:

- **Research graph:** chosen persona → analyst stack (parallel) → synthesis → memo artifact
- **Committee graph:** moderator → round-robin persona turns (streamed live) → Risk interjection → PM summary → transcript artifact + decision
- **Backtest graph:** time-step loop running research/committee as-of each date, updating portfolio and scoring personas

Graphs live in `app/agents/graphs/`. One file per graph. Do not inline graph logic into API routes.

## 7. Streaming contract (backend ↔ renderer)

Client opens `ws://localhost:8787/ws/jobs/{job_id}` after `POST /jobs`. Server pushes JSON lines:

```json
{"type": "token", "agent": "buffett", "text": "..."}
{"type": "tool_call", "agent": "buffett", "name": "get_financials", "input": {...}}
{"type": "tool_result", "agent": "buffett", "name": "get_financials", "output": {...}}
{"type": "status", "agent": "buffett", "status": "done"}
{"type": "artifact", "artifact": {...}}
{"type": "job_done", "cost_usd": 0.23}
{"type": "error", "message": "..."}
```

Renderer demultiplexes by `agent`. The Committee Room uses this to render each persona's turn in its own stream; the Research Desk uses it to show a progress tree. No polling. If the WS drops, client reconnects and server replays from the job's event log (persisted in `job_events` table).

## 8. Model selection policy

Use the Anthropic SDK (`anthropic.AsyncAnthropic`). Config in `apps/backend/app/config.py`.

- `claude-opus-4-7` — PM, deep-thesis personas (Buffett, Druckenmiller, Burry). Used sparingly.
- `claude-sonnet-4-6` — Default for personas and analysts. 80%+ of calls.
- `claude-haiku-4-5` — Sentiment, hot-loop calls inside the backtester, moderator routing.

Per-persona model is stored in `personas.model` and overridable from the Roster UI. **Never hard-code a model inside an agent file** — always read from the persona row.

Always stream (`client.messages.stream(...)`). Never call the non-streaming endpoint from an agent.

## 9. Cost controls (non-negotiable)

- Every job has a `budget_usd` (default 0.50). Track cost in-process using SDK-reported token counts × a pricing table in `app/config.py`.
- If a job exceeds its budget, abort cleanly — emit a `StatusEvent("budget_exceeded")`, save partial artifacts, close the job.
- Daily spend cap in `.env` (`DAILY_BUDGET_USD`). Enforced in the job router before kickoff.
- Log every API call's token counts to `api_calls` table. Exposed on the Office dashboard.

Never retry a failed job automatically without the user clicking retry. Silent retries burn budget.

## 10. Commands

```bash
# One-time
pnpm install
cd apps/backend && poetry install && cp ../../.env.example ../../.env

# Dev (two terminals)
pnpm dev:desktop                          # Electron + Vite
pnpm dev:backend                          # uvicorn with reload

# Quality gates — run before every commit
pnpm typecheck
pnpm lint
pnpm test
cd apps/backend && poetry run pytest && poetry run ruff check . && poetry run mypy app

# Build
pnpm build:mac | build:win | build:linux
```

If you add a command, add it here.

## 11. Code conventions

- **TypeScript:** strict mode on. No `any` — use `unknown` and narrow. Renderer talks to main via typed `window.api` only, never directly to the backend.
- **Python:** Pydantic v2 models for every boundary (HTTP, WS, agent I/O). `ruff` for lint, `mypy --strict` for types. No bare `except`.
- **Shared types:** Pydantic → TS via `datamodel-code-generator` into `packages/shared-types/`. Regenerate on backend schema changes.
- **Errors surface to the user.** Never swallow. Every caught exception becomes either a `StatusEvent("error", ...)` on a job or an HTTP error with a user-readable `detail`.
- **No secrets in logs.** API keys, ticker positions, and portfolio values are redacted by the logger formatter (`app/logging.py`).
- **Tests:** unit tests next to source (`*.test.ts`, `test_*.py`). One end-to-end test per job type lives in `apps/backend/tests/e2e/` and uses a mocked Anthropic client.

## 12. Phased build plan

Each phase must be demoable and shippable on its own.

| Phase | Deliverable | Definition of done |
|-------|-------------|--------------------|
| 0 | Foundation | Scaffolded app, streaming debug panel, one hard-coded persona. |
| 1 | Research Desk (slice) | 3 personas + 2 analysts + job queue + memo artifact viewer. Real NVDA memo readable. |
| 2 | Roster | Full roster CRUD UI. Per-persona model + prompt editable. Performance table wired (empty OK). |
| 3 | Committee Room | Multi-agent debate with per-persona streaming, Risk interjection, PM decision, transcript artifact. |
| 4 | Office + Trading Floor | Dashboard over jobs/portfolio. Ambient spatial view of active agents. |
| 5 | Time Machine | As-of-date data loading, time-stepped backtester, persona scoreboard populated. |

Do not build ahead. If a feature feels like it belongs in a later phase, write it down in `docs/later.md` and move on.

## 13. Adding things (recipes)

- **New persona:** insert row in `personas`, add prompt template to `app/agents/personas/<name>.md`, add a `<name>.py` that loads the template and implements `Agent`. Register in `app/agents/registry.py`. Add fixture test.
- **New analyst:** same as persona but under `app/agents/analysts/`. Analysts are called by the synthesis node in the Research graph — wire it there.
- **New job type:** Pydantic schema for inputs/outputs, LangGraph graph under `app/agents/graphs/`, route in `app/api/jobs.py`, renderer room or panel for the inputs and artifact view. Update the `jobs.type` enum.
- **New tool:** `app/tools/<name>.py` exposing a single async function. Register with the Anthropic tool-use definition in `app/agents/tools.py`. Stub in tests — never hit a live market data provider in tests.

## 14. Do not touch / safety rails

These are hard rules. Ask the user before relaxing any of them.

- **No real trades.** No brokerage integrations, no order-execution code, no API calls to Alpaca / IBKR / anything that can move money. If the user asks for this, stop and raise the regulatory conversation (advisor registration, custody, compliance) before writing a line of code.
- **Local-first.** Portfolio, positions, API keys, and artifacts stay on the user's machine. No telemetry. No cloud sync. No analytics SDKs.
- **Never log API keys or position values at INFO or above.** Redaction in `app/logging.py` is load-bearing — don't bypass it.
- **Never call the Anthropic API without a per-job budget.** No exceptions, including tests (use the mock client).
- **Never retry automatically.** User-initiated only.
- **No network calls in tests.** Mock the Anthropic client and all market-data tools.
- **Do not rename core schema fields without writing a migration.** `jobs`, `artifacts`, `personas`, `portfolio` are the stable contract between front and back.
- **Keep CLAUDE.md current.** If this file drifts from the code, fix the file in the same PR as the code change.

## 15. When in doubt

Prefer the smaller change. Prefer the simpler graph. Prefer paraphrasing an investor's style over quoting them. Prefer explicit budget failures over silent degradation. Ask the user before adding dependencies, switching stacks, or building ahead of the current phase.
