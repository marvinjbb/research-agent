# Research Agent

A deliberately small Python 3.12/FastAPI foundation for a bounded multi-agent research
proof of concept. This phase provides the API shell, request validation, tests, linting,
and architecture documentation. It does not perform research yet.

## Current capabilities

- `GET /health` returns `{"status":"ok"}`.
- `ResearchRequest` validates one question and a `quick` or `deep` research depth.
- pytest and Ruff provide the initial quality gates.

## Local setup

Python 3.12 is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

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

