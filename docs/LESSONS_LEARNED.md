# Lessons Learned

## Grounding must be owned by the application

Asking a model to reproduce an exact excerpt proved fragile: harmless surrounding quotes
could break exact validation, while relaxing comparison would weaken provenance. The
durable correction was to create immutable evidence candidates and let the model select
IDs. Application code now resolves the exact stored text.

The same failure pattern appeared in synthesis. Asking the model to restate aggregated
facts made the final boundary depend on exact text reproduction. Selecting claim,
evidence, and uncertainty IDs keeps generation useful while making factual assembly
deterministic and testable.

## Bounded orchestration is an engineering feature

Two to five workers, two searches per worker, ten sources per worker, no recursive
spawning, and no automatic retries make cost and failure behavior understandable. More
agents would not automatically produce better research; it would multiply provider cost,
latency, and duplicate work.

## Partial success needs an explicit contract

Treating every worker failure as a job failure discards useful evidence. Ignoring failures
hides reduced coverage. Ordered outcome records preserve both successes and failure
metadata, while an all-worker failure remains a hard stop.

## Determinism is preferable to impressive-looking heuristics

Exact URL deduplication and normalized-identical claim merging are limited but predictable.
The service deliberately avoids pretending that string similarity is reliable conflict
analysis. Distinct claims remain visible to synthesis, and the limits are documented.

## Provenance is not the same as truth

Evidence IDs establish which retrieved excerpt supports a claim and prevent invented
citations. They do not guarantee that search results are authoritative, current, complete,
or that every model-authored claim is semantically entailed. Those require source-quality
controls and a scored evaluation program.

Structured Outputs strengthen shape and selection constraints; they do not guarantee
semantic correctness. A schema-valid claim can still overreach its excerpt, and a
schema-valid source can still be promotional, stale, dependent on another source, or wrong.

## Search quality and synthesis quality are separate

A report can fail because retrieval returned weak snippets, a worker selected unsupported
evidence, or final synthesis selected an invalid relationship. These boundaries need
separate evaluation. A grounding rejection proves that the application contract was not
satisfied; it does not by itself identify the responsible component.

The September 2026 production observations made the distinction concrete. Two unsupported
workers were isolated while validated work still produced a report. A different run reached
final synthesis but returned no report because the final evidence relationship failed
validation. Failing closed was safer than silently returning unsupported material.

## Source frequency can mislead presentation

Repeated citations to one displayed claim can make a source look more prominent than a
source that supports several distinct claims. The backend preserves relationships but does
not rank authority. Presentation-level ordering belongs to the frontend and should clearly
distinguish raw citation occurrences from distinct-claim coverage.

## Provider boundaries made the system testable

Planner, search, worker analysis, and synthesis protocols let 154 tests run without paid
calls. The same separation keeps SDK-specific code out of orchestration and makes provider
failure semantics explicit.

## A synchronous demo is a deliberate tradeoff

Returning one final report makes the portfolio interaction simple, but requires a long
proxy timeout and loses in-flight work on restart. Durable async jobs would be the next
architectural step only if traffic or reliability requirements justify persistence and a
queue.

## Smoke tests and quality benchmarks answer different questions

A controlled production smoke test can show that routing, providers, validation, and error
mapping work together. It cannot establish general research accuracy, source quality,
latency guarantees, or reliability from three questions. Formal quality claims require a
versioned labeled dataset, repeatable scoring, and enough runs to support the conclusion.
