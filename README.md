# Research Agent

A deliberately bounded Python 3.12/FastAPI research proof of concept. Phase 2 adds only
LLM-assisted planning behind an application-owned interface. It does not execute research.

## Current capabilities

- `GET /health` returns `{"status":"ok"}`.
- `ResearchRequest` validates one question and a `quick` or `deep` research depth.
- `POST /research/plan` returns a validated plan containing 2–5 focused assignments.
- OpenAI SDK code is isolated behind the `ResearchPlanner` protocol.
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
environment settings. Never put credentials in `.env.example` or frontend code.

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

The response is a plan only. It does not run workers, search, or produce a report.

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
