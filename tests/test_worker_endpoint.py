from typing import Any

import pytest
from fastapi.testclient import TestClient

from research_agent.main import app, get_worker
from research_agent.schemas import WorkerAssignment
from research_agent.search.base import SearchProviderError, SearchTimeoutError
from research_agent.workers.base import (
    EmptySearchResultsError,
    WorkerEvidenceError,
    WorkerProviderError,
    WorkerTimeoutError,
)

ASSIGNMENT = {
    "worker_id": "worker-1",
    "focused_task": "Assess adoption",
    "investigation_focus": "Investigate current production adoption",
    "evidence_to_find": ["Recent surveys"],
}


class FakeWorker:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def research(self, assignment: WorkerAssignment) -> dict[str, Any]:
        if self.error:
            raise self.error
        return {
            "worker_id": assignment.worker_id,
            "assignment": assignment,
            "claims": [
                {
                    "claim": "Adoption increased.",
                    "evidence": [{"source_id": "source-1", "evidence": "Survey reports growth."}],
                }
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "title": "Survey",
                    "url": "https://example.com/survey",
                    "snippet": "Survey reports growth.",
                }
            ],
            "uncertainties": ["Limited sample."],
        }


def request_with(worker: FakeWorker):
    app.dependency_overrides[get_worker] = lambda: worker
    try:
        return TestClient(app, raise_server_exceptions=False).post(
            "/research/worker", json=ASSIGNMENT
        )
    finally:
        app.dependency_overrides.clear()


def test_single_worker_endpoint_returns_validated_result() -> None:
    response = request_with(FakeWorker())

    assert response.status_code == 200
    assert response.json()["worker_id"] == "worker-1"
    assert response.json()["claims"][0]["evidence"][0]["source_id"] == "source-1"


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (EmptySearchResultsError(), 424),
        (SearchProviderError(), 502),
        (WorkerProviderError(), 502),
        (SearchTimeoutError(), 504),
        (WorkerTimeoutError(), 504),
        (WorkerEvidenceError(), 422),
    ],
)
def test_single_worker_endpoint_maps_errors(error: Exception, status_code: int) -> None:
    assert request_with(FakeWorker(error)).status_code == status_code


def test_unconfigured_search_provider_returns_service_unavailable(monkeypatch) -> None:
    monkeypatch.chdir("/")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    response = TestClient(app).post("/research/worker", json=ASSIGNMENT)

    assert response.status_code == 503


def test_non_basic_search_configuration_is_rejected(monkeypatch) -> None:
    monkeypatch.chdir("/")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_SEARCH_DEPTH", "advanced")

    response = TestClient(app).post("/research/worker", json=ASSIGNMENT)

    assert response.status_code == 503
