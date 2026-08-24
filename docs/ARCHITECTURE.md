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

Phases 2–5 implement planning, bounded concurrent worker execution, deterministic evidence
aggregation, structured conflict analysis, a cited final report, and the complete
request-scoped workflow.

## Component responsibilities

- **FastAPI:** accepts and validates one research question per request and exposes the
  complete workflow through `POST /research`.
- **Research Orchestrator:** decomposes the question into specific assignments, chooses
  between two and five workers, and coordinates their bounded execution. Phase 4's
  synthesis layer aggregates their validated evidence into the final report.
- **Research Workers:** run concurrently inside the same Python service. Each
  receive one explicit assignment rather than an unrestricted goal.
- **Web Search:** Tavily Basic Search retrieves current external sources behind the
  application-owned `SearchProvider` interface.
- **Structured Evidence:** each successful worker returns sources, claims, evidence, and
  uncertainties using validated schemas.
- **Analysis and synthesis:** deterministic aggregation deduplicates identical URLs and
  normalized-identical claims. An application-owned synthesis boundary identifies
  conflicts and organizes only validated claims/evidence into a cited report.

## v1 boundaries

- One research question per request.
- The orchestrator chooses between 2 and 5 workers.
- Workers are concurrent tasks inside one Python service, not independently deployed
  services.
- Every worker receives a specific research assignment.
- Worker output contains structured findings, sources, claims, and uncertainties.
- Final reports are grounded in validated worker evidence and contain citations.
- No RAG or vector database.
- No long-term memory.
- No persistence or database initially.
- No recursive or unlimited agent spawning.
- No frontend.
- One production container for the existing Python service; no distributed workers.
- No repository-owned Nginx or VPS host-port configuration.

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
  → immutable application-owned EvidenceCandidate records
  → WorkerResearchProvider interface
  → selected evidence IDs resolved by the application
  → validated WorkerResult
```

The worker and search adapter are separate application layers. No provider SDK belongs in
`SingleResearchWorker`. It deterministically assigns stable IDs to exact, bounded excerpts
from normalized snippets and supplies those immutable candidates to the analysis provider.
The model selects evidence IDs instead of reproducing text. Application code rejects
unknown IDs and resolves valid selections into `ClaimEvidence`, so the provider cannot
invent or modify evidence text. `WorkerResult` still validates source identity and exact
excerpt containment. Evidence IDs travel with validated evidence through aggregation and
final citations; conflicting ID-to-source/text mappings fail validation. The Tavily adapter
uses Basic Search behind `SearchProvider`; no
Tavily code belongs in worker logic.

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

## Phase 4 synthesis boundary

```text
ResearchExecutionResult
  → EvidenceAggregator
  → EvidenceBundle
  → ResearchSynthesizer interface
  → OpenAI Structured Outputs adapter
  → SynthesisDraft
  → application grounding validation
  → FinalResearchReport
```

Only successful `WorkerResult` objects contribute factual evidence. Identical URLs become
one global source while retaining every snippet, validated excerpt, and original
`(worker_id, worker_source_id)` provenance record. Claims are merged only when their
case/whitespace-normalized text is identical. Exact containment is flagged as obvious
overlap, but distinct claims are preserved.

The model receives only `EvidenceBundle` and returns application-owned claim, evidence,
and uncertainty IDs. Application code resolves exact claim wording, citations, source
references, and uncertainty wording into the unchanged final-report contract. Conflicts
select at least two claim positions. Recommendations and conflict summaries may be authored
as inference, but their factual support is selected by ID. Worker uncertainties and failed-
worker summaries retain their original attribution. Final validators recheck all resolved
claims and citations as defense in depth.

Material-conflict classification is intentionally provider-driven in v1 because reliable
semantic conflict detection cannot be implemented with exact string rules alone. The
application never merges distinct claims, supplies every claim to the provider, requires
separately cited positions for any reported conflict, and validates those positions. It
does not claim that every latent semantic conflict can be detected without later
evaluation or semantic analysis.

## Phase 5 end-to-end workflow boundary

```text
ResearchRequest
  → ResearchWorkflow
  → ResearchPlanner
  → ResearchPlan
  → ParallelResearchOrchestrator
  → ResearchExecutionResult
  → ResearchSynthesisService
  → FinalResearchReport
```

`ResearchWorkflow` is application-owned and independent of FastAPI. It adds no planning,
search, worker, aggregation, or synthesis behavior; it validates and passes each existing
application-owned contract to the next proven service. All state is local to one request.
The primary endpoint accepts no worker count, persistence identifier, or background-job
configuration.

Known planner, all-worker, and synthesis failures retain their existing typed exceptions
and HTTP mappings. Pydantic failures at workflow handoffs become an explicit invalid
structured-output error. Unexpected programming exceptions are not caught or disguised as
provider failures.

## Deployment container boundary

```text
VPS runtime environment
  → runtime-only OpenAI and Tavily variables
  → non-root Research Agent container
  → Uvicorn on 0.0.0.0:8000
  → FastAPI /health and /research
```

The multi-stage Docker build creates a wheel in a disposable builder and installs only the
project and runtime dependencies into the final Python 3.12 slim image. Source-control
metadata, tests, documentation, local virtual environments, caches, and `.env` never enter
the build context. The image declares port 8000 but does not select a VPS host port. A
standard-library health check verifies both the HTTP status and exact health payload.

The container does not change application architecture: all 2–5 workers remain bounded
async tasks in one service. OpenAI and Tavily adapters still receive credentials from
runtime environment variables. Nginx routing, TLS, and host-port selection belong to the
VPS deployment layer and are intentionally absent from this repository.

## Public API boundary

Browser CORS permits only the single HTTPS origin supplied by `CORS_ALLOWED_ORIGIN`
(`https://marvinjb.dev` by default). Credentials are not enabled, and allowed browser
methods and headers are limited to the JSON research request.

All provider-backed POST routes share two process-local bounds: a fixed request window and
a maximum number of active requests. Defaults allow ten accepted requests per ten minutes
and two concurrent provider-backed requests across the container. Rejections return HTTP 429
with `Retry-After`. This global policy intentionally avoids trusting client-controlled
forwarding headers and remains reliable behind the reverse proxy. It resets on container
restart and would not coordinate across replicas; those are accepted constraints while v1
runs as one container. `/health` remains an unlimited process-level liveness check.

Because the endpoint returns only after the bounded workflow completes, the external
reverse proxy needs an upstream response timeout long enough for quick and deep research.
The initial operational recommendation is 300 seconds, followed by measurement-based
tuning. No reverse-proxy files belong in this application repository.
