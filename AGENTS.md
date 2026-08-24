# Research Agent Contributor Instructions

## Purpose

Build a production-minded but deliberately bounded research-agent portfolio project.
Favor clear interfaces, source grounding, tests, and explainable engineering decisions.

## Current phase

Phase 5 exposes one request-scoped `ResearchWorkflow` that composes the existing planner,
parallel orchestrator, and synthesis service behind `POST /research`. Do not duplicate or
redesign any phase logic. Automated tests mock major boundaries; controlled real workflow
calls require explicit approval. Do not add background jobs, fuzzy clustering,
replacement workers, automatic retries, recursive spawning, persistence, RAG, a frontend,
Docker, or deployment unless the project owner explicitly advances the roadmap.

Worker analysis uses immutable application-generated evidence candidates. Provider output
may select candidate IDs only; application code owns and resolves the exact evidence text.
Never relax this boundary with fuzzy, semantic, or case-insensitive evidence matching.
Synthesis follows the same rule: provider output selects claim, evidence, and uncertainty
IDs. Application code owns final factual statements, citations, sources, and uncertainty
text; only recommendation guidance/rationale and conflict summaries may be model-authored.
Diagnostic logs may include only application-format record IDs. Redact malformed IDs before
logging because provider-controlled strings can otherwise contain sensitive content.

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
