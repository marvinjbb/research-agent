from fastapi.testclient import TestClient

from research_agent.main import app, get_planner
from research_agent.planning.base import PlannerProviderError, PlannerTimeoutError
from research_agent.schemas import ResearchPlan, ResearchRequest, WorkerAssignment


class FakePlanner:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[ResearchRequest] = []

    async def plan(self, request: ResearchRequest) -> ResearchPlan:
        self.requests.append(request)
        if self.error:
            raise self.error
        return ResearchPlan(
            original_question=request.question,
            objective="Evaluate the question.",
            strategy=f"Use a {request.depth.value} planning strategy.",
            worker_count=2,
            assignments=[
                WorkerAssignment(
                    worker_id="worker-1",
                    focused_task="Supporting evidence",
                    investigation_focus="Investigate evidence supporting the premise",
                    evidence_to_find=["Primary sources"],
                ),
                WorkerAssignment(
                    worker_id="worker-2",
                    focused_task="Alternative perspectives",
                    investigation_focus="Investigate counterarguments and risks",
                    evidence_to_find=["Conflicting evidence"],
                ),
            ],
        )


def test_planning_endpoint_returns_validated_plan() -> None:
    planner = FakePlanner()
    app.dependency_overrides[get_planner] = lambda: planner
    try:
        response = TestClient(app).post(
            "/research/plan",
            json={"question": "Is RAG still important?", "depth": "deep"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["worker_count"] == 2
    assert len(response.json()["assignments"]) == 2
    assert planner.requests[0].depth.value == "deep"


def test_endpoint_rejects_invalid_planner_response() -> None:
    class InvalidPlanner:
        async def plan(self, request: ResearchRequest) -> dict[str, object]:
            return {
                "original_question": request.question,
                "objective": "Objective",
                "strategy": "Strategy",
                "worker_count": 1,
                "assignments": [],
            }

    app.dependency_overrides[get_planner] = InvalidPlanner
    try:
        response = TestClient(app, raise_server_exceptions=False).post(
            "/research/plan",
            json={"question": "Question", "depth": "quick"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500


def test_provider_failure_returns_bad_gateway() -> None:
    app.dependency_overrides[get_planner] = lambda: FakePlanner(error=PlannerProviderError())
    try:
        response = TestClient(app).post(
            "/research/plan", json={"question": "Question", "depth": "quick"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502


def test_provider_timeout_returns_gateway_timeout() -> None:
    app.dependency_overrides[get_planner] = lambda: FakePlanner(error=PlannerTimeoutError())
    try:
        response = TestClient(app).post(
            "/research/plan", json={"question": "Question", "depth": "quick"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504


def test_missing_configuration_returns_service_unavailable(monkeypatch) -> None:
    monkeypatch.chdir("/")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).post(
        "/research/plan", json={"question": "Question", "depth": "quick"}
    )

    assert response.status_code == 503


def test_blank_api_key_returns_service_unavailable(monkeypatch) -> None:
    monkeypatch.chdir("/")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    response = TestClient(app).post(
        "/research/plan", json={"question": "Question", "depth": "quick"}
    )

    assert response.status_code == 503
