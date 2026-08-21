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

Phases 2–3B implement planning through bounded concurrent worker execution and structured
worker outcomes. Deduplication, conflict analysis, synthesis, and the cited report remain
documented targets, not implemented capabilities.

## Component responsibilities

- **FastAPI:** accepts and validates one research question per request and will expose
  research progress/results in a later phase.
- **Research Orchestrator:** decomposes the question into specific assignments, chooses
  between two and five workers, and coordinates their bounded execution. Evidence
  combination remains deferred.
- **Research Workers:** run concurrently inside the same Python service. Each
  receive one explicit assignment rather than an unrestricted goal.
- **Web Search:** Tavily Basic Search retrieves current external sources behind the
  application-owned `SearchProvider` interface.
- **Structured Evidence:** each successful worker returns sources, claims, evidence, and
  uncertainties using validated schemas.
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

No plan is treated as research output. Phase 3B executes its assignments but does not
combine their evidence into conclusions or a report.

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

## Phase 3B orchestration boundary

```text
ResearchPlan (2–5 assignments)
  → ParallelResearchOrchestrator
  → asyncio.gather over one SingleResearchWorker per assignment
  → ordered WorkerExecutionOutcome records
  → ResearchExecutionResult
```

The orchestrator is application-owned and separate from FastAPI. `asyncio.gather`
schedules the fixed assignment list concurrently and returns outcomes in input order.
Each assignment is attempted once. Known worker failures become safe per-worker metadata;
successful grounded results remain available. At least one worker must succeed, otherwise
the orchestrator raises a job-level error mapped to HTTP 424. There are no replacement
workers, automatic retries, recursive spawning, distributed queues, or synthesis.
