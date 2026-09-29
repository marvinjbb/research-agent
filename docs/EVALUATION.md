# Evaluation Strategy

Evaluation must separate application invariants from research quality. Passing structural
grounding proves that a report stayed inside the retrieved evidence set; it does not prove
that the sources were authoritative or that every claim was semantically correct.

## 1. Offline deterministic testing — implemented

The 154-test suite uses injected fake planners, workers, search providers, and synthesizers.
It makes no OpenAI, Tavily, or production calls. Coverage includes schema bounds,
structured-output failures, timeouts, source normalization, evidence-ID resolution,
citation relationships, ordered concurrency, partial failure, deterministic aggregation,
synthesis, API mappings, CORS, process-local rate limiting, observability, and health.

### Grounding matrix

| Case | Expected result |
| --- | --- |
| Known evidence ID belongs to selected claim/source | Exact stored excerpt is resolved |
| Unknown evidence or claim ID | Reject |
| Evidence ID belongs to another claim | Reject |
| Model attempts to supply factual text at synthesis | Schema rejects it |
| Unknown uncertainty ID | Reject |
| Duplicate URL | One aggregate source with preserved provenance |
| Identical normalized claim | Merge evidence and worker provenance |
| Distinct/overlapping claims | Preserve; flag only obvious containment |
| One worker fails | Preserve failure metadata and synthesize successes |
| All workers fail | Stop before synthesis |

### Failure-mode matrix

| Boundary | Covered behavior |
| --- | --- |
| Planner | Missing config, timeout, provider error, invalid 2–5 plan |
| Search | Empty, malformed, duplicate/invalid URLs, timeout, provider error |
| Worker | Unknown/unsupported evidence, malformed result, ID preservation |
| Execution | Out-of-order completion, timeout, partial/all failure |
| Synthesis | Unknown/unrelated IDs, provider error, timeout, malformed draft |
| Public API | Exact CORS, process-local capacity/window limits, `Retry-After` |

## 2. Controlled production smoke and behavior testing — performed

In September 2026, exactly three `quick` jobs were attempted against the deployed service.
No retry was performed. These observations verify specific integration and failure behavior;
they are not an accuracy benchmark, source-quality benchmark, SLA, latency guarantee,
hallucination rate, load test, scientific dataset, or estimate of production failure rate.

### Run 1 — completed without worker failure

**Question:** “What evidence exists on whether AI coding assistants improve developer
productivity and code quality?”

- HTTP 200 in approximately 28.73 seconds.
- 26 aggregated sources.
- 20 evidence-backed claims.
- 0 failed workers.
- A final report was returned.

### Run 2 — partial worker failure with successful report

**Question:** “What are the main security risks of AI agents that can use tools or take
actions in production systems, and what mitigations are supported by evidence?”

- HTTP 200 in approximately 24.29 seconds.
- 8 aggregated sources.
- 7 evidence-backed claims.
- 2 failed workers, each recorded as `worker returned unsupported evidence`.
- The final report was constructed from successful validated worker results.

This run demonstrates partial-failure isolation. It does not prove that partial failure is
always recoverable or that the returned research was complete.

### Run 3 — final synthesis rejected

**Question:** “What does the research say about whether retrieval-augmented generation
reduces hallucinations, and how should RAG systems be evaluated in production?”

- HTTP 422 in approximately 39.52 seconds.
- Final error: `research synthesis contains unsupported evidence`.
- No final report was returned.
- No retry was performed.

The application preferred rejecting unsupported grounding over returning a report that
failed its evidence contract. The observation does not establish the underlying root cause;
separate diagnosis would be required to distinguish model selection, prompt behavior,
source material, ID/aggregation behavior, or another integration defect.

## Grounding failures are evaluation signals

A rejected worker means that worker did not satisfy the application grounding contract.
If another worker succeeds, its validated work may still proceed and the failed-worker
metadata remains visible. A rejected final synthesis means the application cannot construct
a valid final report, so the entire request fails closed.

These failures show that validation prevented unsupported relationships from becoming a
successful output. They do not alone show that a source was factually wrong, that the model
or prompt was solely responsible, or that an application bug was absent.

Earlier controlled implementation checks exposed a different contract problem: models did
not reliably reproduce exact application-owned evidence or claim text. Those observations
led to the current evidence-ID and synthesis-selection contracts. They were not captured as
a versioned scored dataset and therefore do not constitute a provider regression benchmark.

## 3. Formal research-quality evaluation — not implemented

A versioned labeled dataset and scored evaluation harness are still future work. A useful
program should measure, without assuming the answers in advance:

| Dimension | Candidate measurement | Current status |
| --- | --- | --- |
| Search relevance | Human relevance grade per result/question | Not measured |
| Source authority | Rubric by source type and question | No classification or score |
| Freshness | Publication/update date against question need | Metadata not retained |
| Claim entailment | Human/adjudicated claim–excerpt support label | IDs prove provenance only |
| Citation completeness | Factual statement coverage by valid support | Structural coverage enforced |
| Conflict recall | Curated questions with known competing evidence | Not measured |
| Source diversity | Domains, source types, and viewpoint coverage | Not scored |
| Source independence | Organizational/editorial independence | Not classified |
| Quick vs deep quality | Paired rubric for coverage, cost, and latency | Not benchmarked |
| Operational behavior | Latency, cost, validation outcome, rejection rate | No formal dataset |

## Source prominence is not source authority

Production review showed that repeated citation occurrences can overstate apparent
importance: one source cited repeatedly for the same displayed claim can receive a larger
raw reference count than a source supporting several distinct claims. Raw citation
frequency and distinct-claim coverage are different measures.

The backend preserves sources, claims, evidence relationships, and provenance. It does not
rank authority or trustworthiness. Any source ordering performed by the separate portfolio
frontend is presentation logic and must not be described as backend quality ranking.

## Recommended evaluation harness

Create a small versioned set of public questions across stable facts, contested topics,
recent events, and insufficient-evidence cases. Store expected research dimensions—not
golden prose. For each authorized run, record provider/model versions, query count, source
count, latency, token/cost data, validation outcome, citation validity, rejection category,
and human rubric scores. Keep live runs opt-in and separately budgeted; CI must remain fully
offline.

Adversarial cases should include duplicate domains, low-quality SEO sources, promotional
material, conflicting sources, snippets too weak for a requested claim, unrelated evidence
ID selections, prompt injection inside snippets, and partial provider failure. Evaluation
must not relax exact ID relationships merely to improve pass rates.
