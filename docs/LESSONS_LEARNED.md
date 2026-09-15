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

## Provider boundaries made the system testable

Planner, search, worker analysis, and synthesis protocols let 154 tests run without paid
calls. The same separation keeps SDK-specific code out of orchestration and makes provider
failure semantics explicit.

## A synchronous demo is a deliberate tradeoff

Returning one final report makes the portfolio interaction simple, but requires a long
proxy timeout and loses in-flight work on restart. Durable async jobs would be the next
architectural step only if traffic or reliability requirements justify persistence and a
queue.
