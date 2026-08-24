import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from research_agent.config import PublicApiSettings
from research_agent.main import app, enforce_public_research_limit, get_research_workflow
from research_agent.planning.base import PlannerProviderError
from research_agent.public_api import PublicResearchLimiter


def test_cors_allows_portfolio_origin() -> None:
    response = TestClient(app).options(
        "/research",
        headers={
            "Origin": "https://marvinjb.dev",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://marvinjb.dev"
    assert response.headers.get("access-control-allow-credentials") is None


def test_cors_rejects_unknown_origin() -> None:
    response = TestClient(app).options(
        "/research",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com",
        "https://user:pass@marvinjb.dev",
        "https://marvinjb.dev:8443",
        "https://marvinjb.dev/path",
        "https://marvinjb.dev?query=value",
        "https://marvinjb.dev#fragment",
    ],
)
def test_cors_configuration_rejects_every_noncanonical_origin(origin: str) -> None:
    with pytest.raises(ValidationError):
        PublicApiSettings(_env_file=None, CORS_ALLOWED_ORIGIN=origin)


def test_request_window_is_bounded_and_recovers() -> None:
    now = [100.0]
    limiter = PublicResearchLimiter(
        request_limit=2,
        window_seconds=60,
        max_concurrent=2,
        clock=lambda: now[0],
    )

    async def exercise() -> None:
        await limiter.acquire()
        await limiter.release()
        await limiter.acquire()
        await limiter.release()
        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers == {"Retry-After": "60"}

        now[0] += 61
        await limiter.acquire()
        await limiter.release()

    asyncio.run(exercise())


def test_concurrent_work_is_bounded_and_slot_is_released() -> None:
    limiter = PublicResearchLimiter(
        request_limit=3,
        window_seconds=60,
        max_concurrent=1,
    )

    async def exercise() -> None:
        await limiter.acquire()
        with pytest.raises(HTTPException) as exc_info:
            await limiter.acquire()
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail == "research service is currently at capacity"

        await limiter.release()
        await limiter.acquire()
        await limiter.release()

    asyncio.run(exercise())


def limiter_dependency(limiter: PublicResearchLimiter):
    async def dependency():
        await limiter.acquire()
        try:
            yield
        finally:
            await limiter.release()

    return dependency


def test_every_provider_backed_post_route_shares_the_limiter() -> None:
    limiter = PublicResearchLimiter(
        request_limit=1,
        window_seconds=600,
        max_concurrent=2,
    )
    asyncio.run(limiter.acquire())
    asyncio.run(limiter.release())
    app.dependency_overrides[enforce_public_research_limit] = limiter_dependency(limiter)
    try:
        client = TestClient(app)
        for path in (
            "/research/plan",
            "/research/worker",
            "/research/execute",
            "/research/synthesize",
            "/research",
        ):
            response = client.post(path, json={})
            assert response.status_code == 429, path
            assert response.headers["retry-after"]
    finally:
        app.dependency_overrides.clear()


class FailingWorkflow:
    async def research(self, request):
        raise PlannerProviderError


def test_endpoint_failure_releases_concurrency_slot() -> None:
    limiter = PublicResearchLimiter(
        request_limit=3,
        window_seconds=600,
        max_concurrent=1,
    )
    app.dependency_overrides[enforce_public_research_limit] = limiter_dependency(limiter)
    app.dependency_overrides[get_research_workflow] = FailingWorkflow
    try:
        client = TestClient(app)
        body = {"question": "Does an endpoint failure release its slot?", "depth": "quick"}
        first = client.post("/research", json=body)
        second = client.post("/research", json=body)
        assert first.status_code == 502
        assert second.status_code == 502
    finally:
        app.dependency_overrides.clear()
