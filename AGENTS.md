# Research Agent Contributor Instructions

## Purpose

Build a production-minded but deliberately bounded research-agent portfolio project.
Favor clear interfaces, source grounding, tests, and explainable engineering decisions.

## Current phase

Phase 4 aggregates validated successful worker results and produces a structured cited
report behind an application-owned synthesis-provider boundary. Exact URL/claim
deduplication, provenance, grounded citations, explicit conflicts, uncertainties, and
failed-worker metadata are required. Automated tests mock synthesis; controlled real
provider calls require explicit approval. Do not add fuzzy clustering, replacement
workers, automatic retries, recursive spawning, persistence, RAG, a frontend, Docker, or
deployment unless the project owner explicitly advances the roadmap.

## Engineering rules

- Use Python 3.12 and FastAPI.
- Keep request and response contracts in Pydantic models.
- Add tests for observable behavior and validation rules.
- Run `ruff check .` and `pytest` after changes.
- Never commit secrets. Document future variable names in `.env.example`.
- Keep workers as bounded concurrent tasks within one Python service; do not turn them
  into independently deployed services without a new approved decision.
- Record meaningful architecture changes in `docs/DECISIONS.md`.
- Prefer the smallest implementation that completes the current roadmap phase.
