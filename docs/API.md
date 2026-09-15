# API Reference

Base production URL: `https://api.marvinjb.dev`

All request and response bodies are JSON. Provider-backed POST routes share the same
process-local rate/concurrency budget and can return `429` with `Retry-After`. Validation
errors use FastAPI's standard `422` response. Successful responses include `X-Request-ID`.

## Primary workflow

### `POST /research`

Runs planning, 2–5 workers, aggregation, and synthesis in one synchronous request.

```json
{
  "question": "How should production teams secure AI agents?",
  "depth": "quick"
}
```

`question` is trimmed and limited to 1–2,000 characters. `depth` is `quick` or `deep` and
defaults to `quick`. Callers cannot specify worker count. The response is a
`FinalResearchReport` containing the original question, objective, strategy, executive
summary, key findings, important claims, conflicts, uncertainties, recommendations,
evidence claims, sources, and failed-worker summaries.

Expected failures: `424` all workers failed/no successful workers; `502` planner or
synthesis provider failure/invalid workflow structure; `503` missing provider
configuration; `504` planning or synthesis timeout.

## Health

### `GET /health`

Process-level liveness; not rate limited.

```json
{"status":"ok"}
```

## Diagnostic phase endpoints

These endpoints expose the proven phases independently. They are useful for development
and remain part of the current public route surface.

### `POST /research/plan`

Accepts `ResearchRequest`; returns a validated `ResearchPlan` with objective, strategy,
worker count, and 2–5 unique focused assignments. It does not search or execute workers.

Failures: `502` provider failure, `503` missing configuration, `504` timeout.

### `POST /research/worker`

Accepts one existing `WorkerAssignment`; performs bounded search and one analysis call;
returns a grounded `WorkerResult` with claims, sources, exact evidence, and uncertainties.

Failures: `422` unsupported evidence, `424` no usable sources, `502` provider failure,
`503` missing configuration, `504` timeout.

### `POST /research/execute`

Accepts a validated `ResearchPlan`; executes its fixed assignments concurrently; returns
an ordered `ResearchExecutionResult` with success/failure outcome per worker. It does not
synthesize. Returns `424` with bounded worker failure metadata if every worker fails.

### `POST /research/synthesize`

Accepts a validated `ResearchExecutionResult`; aggregates only successful worker evidence
and returns a `FinalResearchReport`. It performs no search and executes no workers.

Failures: `422` unsupported synthesis evidence, `424` no successful workers, `502`
provider failure, `503` missing configuration, `504` timeout.

## CORS and timeouts

Browser CORS permits the configured portfolio origin (default `https://marvinjb.dev`),
`POST`/`OPTIONS`, and `Content-Type`; credentialed browser requests are disabled. The
workflow is synchronous, so the production reverse proxy is configured with a 300-second
upstream response timeout. Provider timeouts remain bounded separately.
