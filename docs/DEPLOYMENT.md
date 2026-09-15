# Deployment Runbook

This documents the verified single-container production shape. It intentionally does not
store VPS-specific Nginx configuration or credentials in the repository.

## Runtime contract

- Python 3.12 multi-stage image; application installed from a wheel.
- Non-root `research-agent` user.
- Uvicorn listens on `0.0.0.0:8000` inside the container.
- Provider keys and settings are injected at runtime from a root-controlled environment
  file; `.env` never enters Git or the image.
- The operator binds a non-conflicting loopback host port and routes Nginx to it.
- `/health` is the process/container liveness check.
- Nginx must allow a 300-second upstream response timeout for `/research`.

## Required configuration

Start from `.env.example`. Required secrets are `OPENAI_API_KEY` and `TAVILY_API_KEY`.
Review model names, provider timeouts, exact CORS origin, 10/600 request window, and maximum
concurrency of 2. Never print the resulting environment file in deployment logs.

## Release procedure

1. Verify tests, Ruff lint/format, secret scan, and Docker build locally/CI.
2. Transfer a clean immutable release that excludes `.git`, `.env`, caches, tests, and
   local environments.
3. Build/tag the image for the release commit.
4. Start the new container with runtime secrets and a loopback-only host binding.
5. Wait for Docker health and verify the exact `/health` response internally.
6. Point the existing Nginx upstream at the new container only after health succeeds.
7. Run `nginx -t`, then reload Nginx.
8. Verify public HTTPS health, exact CORS behavior, `429`/`Retry-After`, and one bounded
   portfolio request only when provider use is explicitly authorized.
9. Inspect safe JSON telemetry for request correlation and failures without research data.

The current process is operator-run rather than automated continuous deployment. CI proves
the offline tests and image build; it does not deploy.

## Rollback

Retain the previous image/release. If health or smoke verification fails, restore the
previous Nginx upstream/container, validate Nginx, reload, and confirm `/health`. There is
no database migration or persistent application state to roll back. Do not delete the
runtime secret file during a normal code rollback.

## Operational checks

```text
GET /health -> 200 {"status":"ok"}
container user -> non-root research-agent
container port -> 8000
CORS origin -> https://marvinjb.dev
request window -> 10 accepted / 600 seconds (default)
concurrent provider requests -> 2 (default)
```

Telemetry events include `http_request_completed`, `research_plan_completed`,
`research_worker_completed`, `research_sources_normalized`,
`research_workflow_completed`/`failed`, `provider_call_failed`, and
`provider_call_completed`, and `public_request_rejected`. Alerting and metrics are not
implemented; use container/runtime log retention appropriate to the host.

## Troubleshooting

- `503`: verify required runtime variables exist without echoing their values.
- `504`: distinguish planner/synthesis timeout from the Nginx upstream timeout.
- `502`: inspect the safe component/error category; do not log provider response bodies.
- `424`: inspect bounded worker failure metadata; do not automatically retry a paid call.
- `429`: honor `Retry-After`; remember the process-local budget resets on restart.
- Unhealthy container: check port binding and exact `/health` payload before changing
  provider settings.
