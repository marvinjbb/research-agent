# Roadmap

The production v1 workflow and container deployment are complete. Future work should be
driven by measured reliability, quality, and traffic needs rather than phase labels.

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

## Production container and safeguards (complete)

- Build a multi-stage Python 3.12 production image
- Run Uvicorn as a non-root user on internal port 8000
- Keep provider credentials runtime-only and outside the build context
- Add a reliable container health check
- Validate the full application and provider dependencies under Linux
- Restrict browser CORS to the portfolio origin
- Add bounded single-container request and concurrency cost controls
- Document the reverse-proxy timeout requirement without adding VPS configuration

## Highest-value next work

- Add a repeatable, scored provider evaluation dataset and harness.
- Measure search relevance, source authority/freshness, semantic claim support, conflict
  recall, latency, and per-request cost.
- Add a bounded overall workflow deadline and usage telemetry.
- Evaluate full-document retrieval before expanding source or worker budgets.
- Decide whether to restrict intermediate phase endpoints and OpenAPI in production.
- Move to durable asynchronous jobs and shared quotas only if real traffic requires them.

## Explicitly deferred

Persistence, RAG, vector storage, long-term memory, repository-owned Nginx configuration,
automatic retries, and distributed deployment infrastructure remain outside the current
scope. They should be added only when a demonstrated requirement justifies them.
