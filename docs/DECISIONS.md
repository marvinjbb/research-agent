# Architecture Decisions

## ADR-001: One deployable Python service

**Status:** Approved

Workers will be concurrent tasks inside the FastAPI service, not separate deployed
services. This keeps the POC operationally simple while preserving logical boundaries.

## ADR-002: Bounded orchestration

**Status:** Approved

The orchestrator will choose 2–5 workers and give each a specific assignment. Recursive
or unlimited spawning is prohibited, providing predictable cost and execution bounds.

## ADR-003: Source-grounded output without RAG

**Status:** Approved

Workers will eventually return structured findings, sources, claims, and uncertainties.
The final report must cite its sources. Search/retrieval fits this use case; no RAG,
vector database, or long-term memory is needed for v1.

## ADR-004: No persistence initially

**Status:** Approved

The initial request lifecycle is transient. A database would add complexity without a
current persistence or access-pattern requirement.

## ADR-005: Minimal initial request contract

**Status:** Approved

The request contains one trimmed question (maximum 2,000 characters) and a `quick` or
`deep` depth, defaulting to `quick`. Worker count is not caller-controlled because it is
an orchestrator decision.

## ADR-006: Application-owned planner boundary

**Status:** Approved

FastAPI depends on a `ResearchPlanner` protocol rather than the OpenAI SDK. Provider code
is isolated in one adapter so application schemas, tests, and endpoint behavior do not
depend on a specific SDK throughout the codebase.

## ADR-007: Structured planning output with defensive validation

**Status:** Approved

The OpenAI adapter requests Structured Outputs using the application-owned `ResearchPlan`
Pydantic model. The application still validates worker bounds, count agreement, unique
IDs, nonblank assignments, and duplicate focused tasks. Model output is never trusted as
arbitrary application structure.

## ADR-008: Environment-only provider configuration

**Status:** Approved

The API key, model, and timeout come from backend environment variables. Missing
configuration returns HTTP 503, provider failure returns 502, and provider timeout
returns 504. Secrets remain only in ignored local or deployment environment storage.
