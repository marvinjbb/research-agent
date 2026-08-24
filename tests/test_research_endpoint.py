from typing import Any

import pytest
from fastapi.testclient import TestClient

from research_agent.main import app, get_research_workflow
from research_agent.orchestration.parallel import AllWorkersFailedError
from research_agent.planning.base import PlannerProviderError, PlannerTimeoutError
from research_agent.schemas import (
    FinalResearchReport,
    ResearchRequest,
    WorkerAssignment,
    WorkerExecutionOutcome,
)
from research_agent.synthesis.base import (
    SynthesisEvidenceError,
    SynthesisProviderError,
    SynthesisTimeoutError,
)
from research_agent.workflow.service import WorkflowValidationError


def final_report(question: str) -> FinalResearchReport:
    evidence = "Validated evidence supports the claim."
    statement = {
        "statement": "The claim is supported.",
        "claim_ids": ["claim-1"],
        "citations": [{"source_id": "source-1", "evidence": evidence}],
    }
    return FinalResearchReport.model_validate(
        {
            "original_question": question,
            "objective": "Assess the question.",
            "strategy": "Use bounded research.",
            "executive_summary": [statement],
            "key_findings": [statement],
            "important_claims": [statement],
            "uncertainties": [
                {"statement": "Evidence is limited.", "worker_ids": ["worker-1"]}
            ],
            "evidence_claims": [
                {
                    "claim_id": "claim-1",
                    "statement": "The claim is supported.",
                    "evidence": [{"source_id": "source-1", "evidence": evidence}],
                    "worker_ids": ["worker-1"],
                }
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "title": "Validated source",
                    "url": "https://example.com/source",
                    "snippets": [evidence],
                    "validated_excerpts": [evidence],
                    "provenance": [
                        {"worker_id": "worker-1", "worker_source_id": "source-1"}
                    ],
                }
            ],
        }
    )


class FakeWorkflow:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.received: list[ResearchRequest] = []

    async def research(self, request: ResearchRequest) -> FinalResearchReport:
        self.received.append(request)
        if self.error:
            raise self.error
        return final_report(request.question)


def request_with(
    workflow: FakeWorkflow,
    body: dict[str, Any] | None = None,
):
    app.dependency_overrides[get_research_workflow] = lambda: workflow
    try:
        return TestClient(app).post(
            "/research",
            json=body or {"question": "Research question?", "depth": "quick"},
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("depth", ["quick", "deep"])
def test_research_endpoint_returns_final_report(depth: str) -> None:
    workflow = FakeWorkflow()

    response = request_with(
        workflow,
        {"question": "Research question?", "depth": depth},
    )

    assert response.status_code == 200
    assert response.json()["original_question"] == "Research question?"
    assert workflow.received[0].depth.value == depth


def test_caller_cannot_supply_worker_count() -> None:
    workflow = FakeWorkflow()

    response = request_with(
        workflow,
        {"question": "Research question?", "depth": "quick", "worker_count": 5},
    )

    assert response.status_code == 422
    assert workflow.received == []


def test_missing_planning_configuration_returns_service_unavailable(
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir("/")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).post(
        "/research",
        json={"question": "Research question?", "depth": "quick"},
    )

    assert response.status_code == 503


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (PlannerProviderError(), 502),
        (PlannerTimeoutError(), 504),
        (SynthesisProviderError(), 502),
        (SynthesisTimeoutError(), 504),
        (SynthesisEvidenceError(), 422),
        (WorkflowValidationError(), 502),
    ],
)
def test_research_endpoint_maps_workflow_errors(
    error: Exception,
    status_code: int,
) -> None:
    assert request_with(FakeWorkflow(error)).status_code == status_code


def test_all_workers_failed_returns_ordered_failure_metadata() -> None:
    outcomes = []
    for index in range(1, 3):
        worker_assignment = WorkerAssignment(
            worker_id=f"worker-{index}",
            focused_task=f"Research area {index}",
            investigation_focus=f"Investigate area {index}",
            evidence_to_find=[f"Evidence type {index}"],
        )
        outcomes.append(
            WorkerExecutionOutcome(
                worker_id=worker_assignment.worker_id,
                assignment=worker_assignment,
                status="failed",
                error={"code": "timeout", "message": "worker timed out"},
            )
        )

    response = request_with(FakeWorkflow(AllWorkersFailedError(outcomes)))

    assert response.status_code == 424
    assert [
        worker["worker_id"] for worker in response.json()["detail"]["workers"]
    ] == ["worker-1", "worker-2"]
