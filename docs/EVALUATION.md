# Evaluation Strategy

Evaluation focuses on whether the system stays bounded and whether every returned factual
record has a valid path to retrieved evidence. Ordinary evaluation is deterministic and
offline; provider quality evaluation is a separate, explicitly authorized activity.

## Current automated coverage

The 154-test suite uses injected fake planners, workers, search providers, and synthesizers.
It exercises schema bounds, structured-output failures, timeouts, source normalization,
evidence-ID resolution, citation relationships, ordered concurrency, partial failure,
aggregation, synthesis, API mappings, CORS, rate limiting, and container-facing health.

### Grounding matrix

| Case | Expected result |
| --- | --- |
| Known evidence ID belongs to selected claim/source | Exact stored excerpt is resolved |
| Unknown evidence or claim ID | Reject |
| Evidence ID belongs to another claim | Reject |
| Model modifies evidence text | Impossible in selection contract; validators still reject |
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
| Public API | Exact CORS, global process-local capacity/window limits, `Retry-After` |

## Controlled provider observations

During implementation, controlled single-call and end-to-end checks exposed two important
defects: models copied quoted evidence text unreliably, and synthesis copied
application-owned claim text unreliably. Those observations led to the evidence-ID and
selection-ID contracts now enforced in code. The checks were not captured as a versioned,
repeatable scored dataset, so this repository does **not** claim a provider regression
harness or a measured accuracy percentage.

## Quality dimensions still needed

| Dimension | Proposed measurement | Current status |
| --- | --- | --- |
| Search relevance | Human relevance grade per returned source | Not automated |
| Source authority | Domain/source rubric by question type | Not implemented |
| Freshness | Publication/update date and freshness requirement | Metadata not retained |
| Claim entailment | Human or adjudicated claim–excerpt support label | IDs prove provenance only |
| Conflict recall | Curated questions with known competing evidence | Not measured |
| Citation completeness | Factual sentence coverage by valid citations | Structural coverage enforced |
| Quick vs deep quality | Paired rubric for coverage, cost, latency | Not benchmarked |

## Recommended evaluation harness

Create a small versioned set of public questions across stable facts, contested topics,
recent events, and insufficient-evidence cases. Store expected research dimensions—not
golden prose. For every run, record provider/model versions, query count, source count,
latency, token/cost data, validation outcome, citation validity, and human rubric scores.
Keep live runs opt-in and separately budgeted; CI must continue using only deterministic
fakes.

Adversarial cases should include duplicate domains, low-quality SEO sources, conflicting
sources, snippets too weak for the requested claim, model-selected unrelated evidence IDs,
prompt injection embedded in snippets, and partial provider failure. Evaluation must not
relax exact ID relationships to improve pass rates.
