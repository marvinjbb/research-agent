# Roadmap

Work proceeds one bounded phase at a time. Advancing a phase requires explicit approval.

## Phase 1 — Foundation (complete)

- Python 3.12 package and FastAPI application
- Health endpoint
- Initial request schema
- pytest and Ruff
- Architecture and decision documentation

## Phase 2 — Planning contracts and adapter (current)

- Define the validated research-plan and worker-assignment contracts
- Add the provider-neutral planner interface and OpenAI Structured Outputs adapter
- Add `POST /research/plan` with controlled configuration/provider errors
- Test planning schema invariants and provider boundaries without paid calls

## Phase 3 — Worker execution skeleton

- Consume the validated 2–5 assignments produced by Phase 2
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
