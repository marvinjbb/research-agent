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
