# Research Agent Contributor Instructions

## Purpose

Build a production-minded but deliberately bounded research-agent portfolio project.
Favor clear interfaces, source grounding, tests, and explainable engineering decisions.

## Current phase

Phase 2 implements planning only: a request may be converted by an LLM into a validated
plan of 2–5 assignments. Do not execute workers or implement web search, parallelism,
synthesis, citations, persistence, RAG, a frontend, Docker, or deployment unless the
project owner explicitly advances the roadmap.

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
