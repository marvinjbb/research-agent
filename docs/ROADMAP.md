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
- Resolve model-selected immutable evidence candidate IDs into exact source excerpts
- Use a fixed sequential search limit and deterministic test doubles

## Phase 3B — Bounded worker orchestration (complete)

- Consume the validated 2–5 assignments produced by Phase 2
- Execute bounded concurrent worker tasks
- Preserve assignment order and grounded results
- Capture partial failures without retries or replacement workers

## Phase 4 — Grounded synthesis and cited report (complete)

- Aggregate successful worker evidence with provenance
- Deduplicate identical URLs and normalized-identical claims
- Surface conflicts, uncertainties, and partial failures
- Produce a validated final cited report behind a provider interface
- Resolve provider-selected claim, evidence, and uncertainty IDs into application-owned text

## Phase 5 — End-to-end research workflow (complete)

- Compose planning, bounded execution, and synthesis without redesigning them
- Add `POST /research` for one complete request
- Preserve phase-specific validation and failure policies
- Keep all workflow state request-scoped and in memory

## Phase 6 — Production container packaging (current)

- Build a multi-stage Python 3.12 production image
- Run Uvicorn as a non-root user on internal port 8000
- Keep provider credentials runtime-only and outside the build context
- Add a reliable container health check
- Validate the full application and provider dependencies under Linux
- Restrict browser CORS to the portfolio origin
- Add bounded single-container request and concurrency cost controls
- Document the reverse-proxy timeout requirement without adding VPS configuration

## Phase 7 — Evaluation and production hardening

- Add repeatable quality, grounding, and failure-mode evaluations
- Improve source-quality selection and document-level deduplication
- Add cost, timeout, and abuse controls

## Explicitly deferred

Persistence, RAG, vector storage, long-term memory, repository-owned Nginx configuration,
and distributed deployment infrastructure remain outside the current scope. They should
be added only when a demonstrated requirement justifies them.
