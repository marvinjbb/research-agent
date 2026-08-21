# Roadmap

Work proceeds one bounded phase at a time. Advancing a phase requires explicit approval.

## Phase 1 — Foundation (current)

- Python 3.12 package and FastAPI application
- Health endpoint
- Initial request schema
- pytest and Ruff
- Architecture and decision documentation

## Phase 2 — Research contracts

- Define assignments, evidence, source, claim, uncertainty, and final-report schemas
- Define error and progress contracts
- Test schema invariants without calling external services

## Phase 3 — Orchestrator skeleton

- Plan 2–5 specific assignments
- Execute bounded concurrent worker tasks
- Add timeouts, cancellation, retries, and partial-failure behavior
- Use deterministic test doubles before real providers

## Phase 4 — Search and model integration

- Evaluate and select search and LLM providers
- Retrieve sources and produce structured evidence
- Add source-grounding and citation checks
- Add cost, timeout, and abuse controls

## Phase 5 — Analysis and evaluation

- Deduplicate evidence and identify conflicting claims
- Synthesize cited reports
- Add repeatable quality, grounding, and failure-mode evaluations

## Explicitly deferred

Frontend, persistence, RAG, vector storage, long-term memory, Docker, and deployment are
outside the current scope. They should be added only when a demonstrated requirement
justifies them.

