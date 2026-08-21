# Architecture

## Approved target flow

```text
User
  → FastAPI
  → Research Orchestrator
  → 2–5 parallel Research Workers
  → Web Search
  → Structured Evidence
  → Orchestrator
  → Deduplication / Conflict Analysis
  → Synthesis
  → Cited Report
```

Phase 2 implements `FastAPI → Research Planner interface → OpenAI adapter → validated
ResearchPlan`. Worker execution and every later box remain documented targets, not
implemented or simulated capabilities.

## Component responsibilities

- **FastAPI:** accepts and validates one research question per request and will expose
  research progress/results in a later phase.
- **Research Orchestrator:** will decompose the question into specific assignments,
  choose between two and five workers, coordinate them, and combine their evidence.
- **Research Workers:** will run concurrently inside the same Python service. Each will
  receive one explicit assignment rather than an unrestricted goal.
- **Web Search:** will retrieve current external sources. Provider selection is deferred.
- **Structured Evidence:** each worker will eventually return findings, sources, claims,
  and uncertainties using validated schemas.
- **Analysis and synthesis:** the orchestrator will deduplicate overlapping evidence,
  identify conflicts, synthesize grounded conclusions, and create a cited report.

## v1 boundaries

- One research question per request.
- The orchestrator chooses between 2 and 5 workers.
- Workers are concurrent tasks inside one Python service, not independently deployed
  services.
- Every worker receives a specific research assignment.
- Worker output will eventually contain structured findings, sources, claims, and
  uncertainties.
- Final reports must eventually be grounded in sources and contain citations.
- No RAG or vector database.
- No long-term memory.
- No persistence or database initially.
- No recursive or unlimited agent spawning.
- No frontend.
- No deployment or Docker yet.

## Current request boundary

`ResearchRequest` contains a required, trimmed `question` (1–2,000 characters) and a
`depth` of `quick` or `deep`. It intentionally contains no worker count: worker selection
belongs to the orchestrator and remains bounded by the architecture.

## Phase 2 planning boundary

FastAPI depends on the application-owned `ResearchPlanner` protocol. The OpenAI adapter
uses Structured Outputs with `ResearchPlan` as the response schema. Application
validation independently enforces 2–5 assignments, matching worker count, unique IDs,
nonblank content, and unique focused task text. Provider configuration comes from backend
environment variables. Provider failure, timeout, and missing configuration have distinct
HTTP responses.

No plan is treated as research output. Phase 3A can execute one supplied assignment, but
the full assignment set is not orchestrated by this service yet.

## Phase 3A single-worker boundary

```text
WorkerAssignment
  → SingleResearchWorker
  → SearchProvider interface (at most 2 sequential searches)
  → normalized SearchSource records (at most 10 unique URLs)
  → WorkerResearchProvider interface
  → validated WorkerResult
```

The worker and search adapter are separate application layers. No provider SDK belongs in
`SingleResearchWorker`. Every `WorkerClaim` requires evidence, and every evidence reference
must match a source included in the result. Evidence text must also be a verbatim excerpt
from that source's normalized snippet. The application preserves the assignment's worker
ID and rejects unknown citations. The Tavily adapter uses Basic Search and normalizes
provider responses behind `SearchProvider`; no Tavily code belongs in worker logic.
