# Research Agent

A deliberately bounded Python 3.12/FastAPI research proof of concept. It can create a
validated plan and execute that plan's 2–5 assignments concurrently without synthesis.

## Current capabilities

- `GET /health` returns `{"status":"ok"}`.
- `ResearchRequest` validates one question and a `quick` or `deep` research depth.
- `POST /research/plan` returns a validated plan containing 2–5 focused assignments.
- OpenAI SDK code is isolated behind the `ResearchPlanner` protocol.
- `POST /research/worker` researches one existing assignment through separately injected
  Tavily Basic Search and OpenAI analysis boundaries.
- `POST /research/execute` runs every assignment in a validated `ResearchPlan` as a
  bounded in-process task and returns ordered success/failure outcomes.
- pytest and Ruff provide the initial quality gates.

## Local setup

Python 3.12 is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY` only in the ignored `.env`. The model and timeout are also backend
environment settings. Store `TAVILY_API_KEY` there as well; Phase 3A enforces
`TAVILY_SEARCH_DEPTH=basic`. Never put credentials in `.env.example` or frontend code.

Run the API:

```powershell
uvicorn research_agent.main:app --reload
```

Verify it:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
ruff check .
pytest
```

Planning request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/research/plan `
  -ContentType 'application/json' `
  -Body '{"question":"Is RAG still important?","depth":"deep"}'
```

The planning response does not run workers, search, or produce a report. Pass a validated
plan to `POST /research/execute` to run its assignments.

Phase 3A's isolated worker returns claims only when each claim has evidence referencing a
known normalized source. Search is capped at two sequential queries and ten unique sources.
Phase 3B uses `asyncio.gather` to execute 2–5 workers concurrently while preserving plan
order. One failed worker does not discard successful grounded results; all-worker failure
returns HTTP 424. Workers are attempted once with no replacement or automatic retry.
Synthesis and a final cited report remain deferred.

## Project structure

```text
research-agent/
├── src/research_agent/  # FastAPI application and API schemas
├── tests/               # Automated behavior and validation tests
├── docs/                # Architecture, roadmap, and decision records
├── AGENTS.md            # Repository-specific contributor guidance
└── pyproject.toml        # Package, dependency, pytest, and Ruff configuration
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the approved target flow and
[docs/ROADMAP.md](docs/ROADMAP.md) for explicitly deferred work.
