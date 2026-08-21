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

Only FastAPI and the initial request schema exist in the foundation phase. Every later
box is a documented target, not an implemented or simulated capability.

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

