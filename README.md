# Research Agent

A deliberately bounded Python 3.12/FastAPI research proof of concept. It can create a
validated plan, execute 2–5 assignments concurrently, and synthesize their validated
evidence into a cited final report.

## Current capabilities

- `GET /health` returns `{"status":"ok"}`.
- `ResearchRequest` validates one question and a `quick` or `deep` research depth.
- `POST /research/plan` returns a validated plan containing 2–5 focused assignments.
- OpenAI SDK code is isolated behind the `ResearchPlanner` protocol.
- `POST /research/worker` researches one existing assignment through separately injected
  Tavily Basic Search and OpenAI analysis boundaries.
- `POST /research/execute` runs every assignment in a validated `ResearchPlan` as a
  bounded in-process task and returns ordered success/failure outcomes.
- `POST /research/synthesize` aggregates a validated execution and returns a grounded
  final report without rerunning workers or searching the web.
- `POST /research` is the primary endpoint. It accepts only a question and `quick` or
  `deep` depth, then runs the proven planning, worker, and synthesis phases once.
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
Final synthesis uses the same backend-only OpenAI key with separate
`OPENAI_SYNTHESIS_MODEL` and `OPENAI_SYNTHESIS_TIMEOUT_SECONDS` settings.

Production browser access is limited to `CORS_ALLOWED_ORIGIN`, which defaults to
`https://marvinjb.dev`. Provider-backed POST endpoints share process-local cost controls:
ten accepted requests per ten-minute window and two simultaneous requests by
default. Override those bounded values through `RESEARCH_RATE_LIMIT_REQUESTS`,
`RESEARCH_RATE_LIMIT_WINDOW_SECONDS`, and `RESEARCH_MAX_CONCURRENT`. `/health` remains an
unlimited process-level liveness check.

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

## Container

Build the production image from the repository root:

```powershell
docker build -t research-agent:local .
```

Run it with an explicit host-port mapping and the ignored local environment file:

```powershell
docker run --rm --name research-agent-local `
  --env-file .env `
  -p 8000:8000 `
  research-agent:local
```

The image listens on `0.0.0.0:8000` internally. The `-p` value is an operator choice and
is not hard-coded into the image, so the VPS can assign a non-conflicting host port.
Provider keys are supplied only at runtime; `.env` is excluded from Git and the Docker
build context. The image runs as the unprivileged `research-agent` user and includes a
`/health` container health check.

The reverse proxy must allow enough time for the synchronous research response. Start with
a 300-second upstream response timeout and measure real quick/deep latency before tuning it.
This is an operational requirement, not an Nginx configuration stored in this repository.

Verify the running container:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
docker inspect --format='{{.State.Health.Status}}' research-agent-local
```

Planning request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/research/plan `
  -ContentType 'application/json' `
  -Body '{"question":"Is RAG still important?","depth":"deep"}'
```

The planning response does not run workers, search, or produce a report. Pass a validated
plan to `POST /research/execute` to run its assignments.

Complete research request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/research `
  -ContentType 'application/json' `
  -Body '{"question":"Is RAG still important?","depth":"deep"}'
```

The caller cannot select worker count. The planner remains responsible for choosing 2–5
assignments, and all workflow state exists only for this request.

Phase 3A's isolated worker deterministically creates immutable evidence candidates from
normalized source snippets. The analysis model selects candidate IDs; application code
resolves those IDs back to exact excerpts and rejects unknown IDs. Search is capped at two
sequential queries and ten unique sources. Evidence IDs remain attached through aggregation
and final citations, providing an auditable path back to application-owned candidates.
Phase 3B uses `asyncio.gather` to execute 2–5 workers concurrently while preserving plan
order. One failed worker does not discard successful grounded results; all-worker failure
returns HTTP 424. Workers are attempted once with no replacement or automatic retry.
Phase 4 deterministically deduplicates identical URLs and normalized-identical claims,
preserves source/worker provenance, and flags obvious claim containment for provider
review. The synthesis model selects application-owned claim, evidence, and uncertainty
IDs; application code resolves all factual text and citations. Recommendations remain
explicit inference grounded in selected IDs. The model cannot author report facts.
Phase 5's `ResearchWorkflow` composes those existing phases without duplicating their
logic or changing their failure policies.

## Project structure

```text
research-agent/
├── src/research_agent/  # FastAPI application and API schemas
├── tests/               # Automated behavior and validation tests
├── docs/                # Architecture, roadmap, and decision records
├── Dockerfile           # Multi-stage production container image
├── .dockerignore        # Minimal, secret-free Docker build context
├── AGENTS.md            # Repository-specific contributor guidance
└── pyproject.toml        # Package, dependency, pytest, and Ruff configuration
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the approved target flow and
[docs/ROADMAP.md](docs/ROADMAP.md) for explicitly deferred work.
