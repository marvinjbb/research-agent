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

## ADR-009: Separate search, worker, and analysis boundaries

**Status:** Approved

`SingleResearchWorker` coordinates application-owned `SearchProvider` and
`WorkerResearchProvider` protocols. Provider SDKs remain in adapters. Tavily Basic Search
is the approved Phase 3A search provider because it returns source URLs, titles, and
content while preserving an independently testable search boundary.

## ADR-010: Evidence references are application invariants

**Status:** Approved

Every factual `WorkerClaim` requires one or more `ClaimEvidence` records. Each evidence
record must reference a known `SearchSource` in the same `WorkerResult`. The application
rejects changed worker IDs, duplicate sources, unknown citations, blank evidence, and
evidence text that is not a verbatim excerpt from the referenced source snippet.

## ADR-011: Fixed single-worker search bounds

**Status:** Approved

Phase 3A performs at most two sequential searches, requests at most five results per
search, and retains at most ten unique source URLs. It has no loops driven by model output,
recursive spawning, parallel execution, or automatic retries.

## ADR-012: Ordered partial-success orchestration

**Status:** Approved

Phase 3B executes the validated plan's fixed 2–5 assignments concurrently with standard
in-process `asyncio.gather`. One existing `SingleResearchWorker` instance is composed per
assignment; no second worker architecture is introduced. Gathered outcomes retain plan
order even when completion order differs.

Each assignment is attempted exactly once. Known failures become typed, safe per-worker
metadata while successful grounded results are retained. At least one worker must succeed;
if all fail, the job returns HTTP 424. Phase 3B adds no replacement workers, automatic
retries, recursive spawning, distributed queues, evidence combination, or synthesis.

## ADR-013: Deterministic aggregation and claim-bound synthesis

**Status:** Approved

Phase 4 separates deterministic evidence aggregation from model synthesis. Identical URLs
are deduplicated into global source records while preserving all original worker/source
provenance, snippets, and previously validated excerpts. Claims are merged only by exact
case/whitespace-normalized equality; exact containment is flagged as obvious overlap.
There is no fuzzy semantic clustering or embedding-based comparison.

OpenAI remains behind the application-owned `ResearchSynthesizer` protocol and returns a
structured `SynthesisDraft`. Every factual report statement must copy an aggregated worker
claim, reference its claim ID, and cite evidence belonging to that claim. Conflicting
positions remain separately cited, recommendations are explicitly inference, and worker
uncertainties must be copied with attribution. The application injects sources,
provenance, and failed-worker metadata and rejects unknown or unsupported citations.
Material-conflict classification is provider-driven in v1; the deterministic layer
preserves every distinct claim and validates cited conflict positions but does not claim
complete semantic conflict detection without fuzzy or embedding-based analysis.

## ADR-014: Thin request-scoped workflow composition

**Status:** Approved

Phase 5 adds an application-owned `ResearchWorkflow` that calls the existing
`ResearchPlanner`, bounded plan executor, and `ResearchSynthesisService` in sequence. It
validates each application-owned handoff but adds no alternate planning, worker,
orchestration, search, aggregation, or synthesis logic.

Workflow state exists only in local variables for one HTTP request. Existing typed phase
failures pass through for explicit endpoint mapping; only Pydantic handoff failures become
`WorkflowValidationError`. Unexpected programming errors are not caught. The primary
request remains `ResearchRequest`, so callers cannot choose worker count or supply state,
queue, retry, or persistence controls.

## ADR-015: Application-owned immutable evidence candidates

**Status:** Approved

Normalized search snippets are deterministically divided into bounded exact excerpts.
The application assigns stable IDs in source and excerpt order and stores each candidate's
source ID, URL, title, and exact evidence text. The worker analysis provider receives these
candidates and returns claim text plus selected evidence IDs only.

`SingleResearchWorker` rejects unknown IDs and resolves valid selections back to the
application-owned excerpts before constructing `WorkerResult`. The provider cannot supply
or alter evidence text. Evidence IDs remain attached through deterministic aggregation and
final citations, and conflicting or unknown ID mappings fail validation. Existing exact
source-containment validation remains as a second grounding check; no fuzzy matching,
semantic similarity, embeddings, or relaxed comparison is introduced.

## ADR-016: Selection-only synthesis provider contract

**Status:** Approved

The provider-facing `SynthesisDraft` selects application-owned claim IDs, evidence IDs,
and uncertainty IDs instead of reproducing immutable factual text. Application code resolves
exact claim statements, evidence excerpts, source references, and uncertainty wording into
the existing `FinalResearchReport` models. Conflicts select competing positions by claim ID.

Recommendation guidance, rationale, and conflict summaries may remain model-authored
inference, but recommendations must select validated claim and evidence IDs. Unknown IDs or
evidence selected from an unrelated claim fail before final report construction, and all
existing final grounding validators remain defense in depth. Safe diagnostics contain only
validation stage, field path, record IDs, and error type; never prompts, provider bodies,
credentials, evidence excerpts, or source contents. Provider-returned IDs are logged only
when they match application-generated ID formats; malformed IDs are replaced by a fixed
redaction marker.
