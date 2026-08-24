from typing import Any

import pytest
from fastapi.testclient import TestClient

from research_agent.main import app, get_synthesis_service
from research_agent.schemas import FinalResearchReport, ResearchExecutionResult
from research_agent.synthesis.base import (
    SynthesisEvidenceError,
    SynthesisProviderError,
    SynthesisTimeoutError,
)

ASSIGNMENT = {
    "worker_id": "worker-1",
    "focused_task": "Assess evidence",
    "investigation_focus": "Investigate the evidence",
    "evidence_to_find": ["Primary evidence"],
}

EXECUTION = {
    "original_question": "Is the claim supported?",
    "objective": "Assess support.",
    "strategy": "Review the evidence.",
    "worker_count": 2,
    "workers": [
        {
            "worker_id": "worker-1",
            "assignment": ASSIGNMENT,
            "status": "succeeded",
            "result": {
                "worker_id": "worker-1",
                "assignment": ASSIGNMENT,
                "claims": [
                    {
                        "claim": "The claim is supported.",
                        "evidence": [
                            {
                                "source_id": "source-1",
                                "evidence": "The report supports the claim.",
                            }
                        ],
                    }
                ],
                "sources": [
                    {
                        "source_id": "source-1",
                        "title": "Report",
                        "url": "https://example.com/report",
                        "snippet": "The report supports the claim.",
                    }
                ],
                "uncertainties": ["Evidence is limited."],
            },
        },
        {
            "worker_id": "worker-2",
            "assignment": {
                **ASSIGNMENT,
                "worker_id": "worker-2",
                "focused_task": "Assess limitations",
            },
            "status": "failed",
            "error": {"code": "timeout", "message": "worker timed out"},
        },
    ],
}


def final_report() -> FinalResearchReport:
    statement = {
        "statement": "The claim is supported.",
        "claim_ids": ["claim-1"],
        "citations": [
            {
                "source_id": "source-1",
                "evidence": "The report supports the claim.",
            }
        ],
    }
    return FinalResearchReport.model_validate(
        {
            "original_question": "Is the claim supported?",
            "objective": "Assess support.",
            "strategy": "Review the evidence.",
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
                    "evidence": [
                        {
                            "source_id": "source-1",
                            "evidence": "The report supports the claim.",
                        }
                    ],
                    "worker_ids": ["worker-1"],
                }
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "title": "Report",
                    "url": "https://example.com/report",
                    "snippets": ["The report supports the claim."],
                    "validated_excerpts": ["The report supports the claim."],
                    "provenance": [
                        {"worker_id": "worker-1", "worker_source_id": "source-1"}
                    ],
                }
            ],
            "failed_workers": [
                {
                    "worker_id": "worker-2",
                    "assignment": EXECUTION["workers"][1]["assignment"],
                    "code": "timeout",
                    "message": "worker timed out",
                }
            ],
        }
    )


class FakeSynthesisService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def synthesize(
        self,
        execution: ResearchExecutionResult,
    ) -> FinalResearchReport:
        if self.error:
            raise self.error
        return final_report()


def request_with(service: FakeSynthesisService):
    app.dependency_overrides[get_synthesis_service] = lambda: service
    try:
        return TestClient(app).post("/research/synthesize", json=EXECUTION)
    finally:
        app.dependency_overrides.clear()


def test_synthesis_endpoint_returns_validated_report() -> None:
    response = request_with(FakeSynthesisService())

    assert response.status_code == 200
    assert response.json()["sources"][0]["source_id"] == "source-1"
    assert response.json()["failed_workers"][0]["worker_id"] == "worker-2"


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (SynthesisTimeoutError(), 504),
        (SynthesisProviderError(), 502),
        (SynthesisEvidenceError(), 422),
    ],
)
def test_synthesis_endpoint_maps_errors(
    error: Exception,
    status_code: int,
) -> None:
    assert request_with(FakeSynthesisService(error)).status_code == status_code


def test_missing_synthesis_configuration_returns_service_unavailable(
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir("/")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).post("/research/synthesize", json=EXECUTION)

    assert response.status_code == 503
