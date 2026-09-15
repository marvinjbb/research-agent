# Security Policy

## Reporting

Please do not open a public issue for a suspected vulnerability. Contact the repository
owner through the public contact information on [marvinjb.dev](https://marvinjb.dev) with
a concise description, affected component, reproduction steps, and impact. Do not include
live credentials, private research content, or destructive proof-of-concept data.

## Supported version

The current `main` branch is the only supported version. This portfolio service does not
promise security updates for earlier commits.

## Security model

- OpenAI and Tavily credentials are runtime-only backend variables.
- Search, worker count, concurrency, and request volume are bounded.
- Models select application-owned evidence/claim IDs; unknown relationships are rejected.
- Browser CORS is restricted to `https://marvinjb.dev`.
- The container runs as a non-root user.
- Telemetry excludes prompts, questions, source/evidence content, provider bodies, cookies,
  sensitive headers, and credentials.

Known limitations include unauthenticated intermediate endpoints, process-local global
rate limiting, enabled OpenAPI UI, no durable audit store, and no distributed abuse
controls. Do not deploy multiple replicas and assume the current limiter is shared.

Never commit `.env`, API keys, tokens, copied provider responses, or private research data.
