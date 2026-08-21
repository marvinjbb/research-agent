# Roadmap

Work proceeds one bounded phase at a time. Advancing a phase requires explicit approval.

## Phase 1 — Foundation (complete)

- Python 3.12 package and FastAPI application
- Health endpoint
- Initial request schema
- pytest and Ruff
- Architecture and decision documentation

## Phase 2 — Planning contracts and adapter (complete)

- Define the validated research-plan and worker-assignment contracts
- Add the provider-neutral planner interface and OpenAI Structured Outputs adapter
- Add `POST /research/plan` with controlled configuration/provider errors
- Test planning schema invariants and provider boundaries without paid calls

## Phase 3A — One bounded research worker (complete)

- Accept one assignment produced by Phase 2
- Define separate search and worker-analysis provider boundaries
- Integrate bounded Tavily Basic Search and OpenAI Structured Outputs adapters
- Enforce source-grounded claims in a structured worker result
- Use a fixed sequential search limit and deterministic test doubles

## Phase 3B — Bounded worker orchestration (current)

- Consume the validated 2–5 assignments produced by Phase 2
- Execute bounded concurrent worker tasks
- Preserve assignment order and grounded results
- Capture partial failures without retries or replacement workers

## Phase 4 — Provider and source-quality hardening

- Improve source-quality selection and document-level deduplication
- Evaluate richer source retrieval only if snippets prove insufficient
- Add cost, timeout, and abuse controls

## Phase 5 — Analysis and evaluation

- Deduplicate evidence and identify conflicting claims
- Synthesize cited reports
- Add repeatable quality, grounding, and failure-mode evaluations

## Explicitly deferred

Frontend, persistence, RAG, vector storage, long-term memory, Docker, and deployment are
outside the current scope. They should be added only when a demonstrated requirement
justifies them.
