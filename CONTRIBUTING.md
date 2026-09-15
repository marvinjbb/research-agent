# Contributing

This is a deliberately bounded portfolio service. Changes should preserve its application-
owned contracts and avoid adding infrastructure without a demonstrated requirement.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --constraint requirements.lock -e ".[dev]"
```

Provider credentials are not needed for the offline suite. If manual provider verification
is explicitly authorized, put secrets only in an ignored `.env` based on `.env.example`.

## Quality gates

```powershell
pytest
ruff check .
ruff format --check .
git diff --check
docker build -t research-agent:local .
```

Add deterministic tests for behavior and failure paths. Mock provider boundaries; CI must
never call OpenAI, Tavily, or production. Keep public schema changes intentional and update
`docs/API.md`, architecture decisions, and tests together.

## Design constraints

- Keep 2–5 in-process workers and at most two searches/worker unless a new decision is
  approved.
- Preserve exact evidence/claim/source ID relationships. Do not add fuzzy grounding.
- Do not log research questions, prompts, evidence/source content, provider bodies,
  credentials, cookies, or sensitive headers.
- Do not add RAG, embeddings, persistence, queues, retries, recursive agents, or distributed
  services merely to make the architecture look larger.
