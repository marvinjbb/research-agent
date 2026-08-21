from fastapi.testclient import TestClient

from research_agent.main import (
    app,
    get_research_orchestrator,
)
from research_agent.orchestration.parallel import AllWorkersFailedError
from research_agent.schemas import (
    ResearchExecutionResult,
    ResearchPlan,
    WorkerExecutionOutcome,
)

PLAN = {
    "original_question": "How is this technology used?",
    "objective": "Assess current use.",
    "strategy": "Divide the evidence into focused areas.",
    "worker_count": 2,
    "assignments": [
        {
            "worker_id": f"worker-{index}",
            "focused_task": f"Research area {index}",
            "investigation_focus": f"Investigate evidence area {index}",
            "evidence_to_find": [f"Evidence type {index}"],
        }
        for index in range(1, 3)
    ],
}


class FakeOrchestrator:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def execute(self, plan: ResearchPlan) -> ResearchExecutionResult:
        if self._fail:
            raise AllWorkersFailedError(
                [
                    WorkerExecutionOutcome.model_validate(
                        {
                            "worker_id": assignment.worker_id,
                            "assignment": assignment,
                            "status": "failed",
                            "error": {
                                "code": "provider_failure",
                                "message": "worker provider failed",
                            },
                        }
                    )
                    for assignment in plan.assignments
                ]
            )
        outcomes = []
        for assignment in plan.assignments:
            evidence = f"Evidence for {assignment.worker_id}."
            outcomes.append(
                {
                    "worker_id": assignment.worker_id,
                    "assignment": assignment,
                    "status": "succeeded",
                    "result": {
                        "worker_id": assignment.worker_id,
                        "assignment": assignment,
                        "claims": [
                            {
                                "claim": "Grounded claim.",
                                "evidence": [
                                    {"source_id": "source-1", "evidence": evidence}
                                ],
                            }
                        ],
                        "sources": [
                            {
                                "source_id": "source-1",
                                "title": "Evidence",
                                "url": f"https://example.com/{assignment.worker_id}",
                                "snippet": evidence,
                            }
                        ],
                        "uncertainties": ["Limited evidence."],
                    },
                }
            )
        return ResearchExecutionResult(
            original_question=plan.original_question,
            objective=plan.objective,
            strategy=plan.strategy,
            worker_count=plan.worker_count,
            workers=outcomes,
        )


def request_with(orchestrator: FakeOrchestrator):
    app.dependency_overrides[get_research_orchestrator] = lambda: orchestrator
    try:
        return TestClient(app).post("/research/execute", json=PLAN)
    finally:
        app.dependency_overrides.clear()


def test_execute_endpoint_returns_ordered_grounded_outcomes() -> None:
    response = request_with(FakeOrchestrator())

    assert response.status_code == 200
    assert [worker["worker_id"] for worker in response.json()["workers"]] == [
        "worker-1",
        "worker-2",
    ]


def test_execute_endpoint_rejects_all_worker_failure() -> None:
    response = request_with(FakeOrchestrator(fail=True))

    assert response.status_code == 424
    assert response.json()["detail"]["message"] == "all research workers failed"
    assert len(response.json()["detail"]["workers"]) == 2
