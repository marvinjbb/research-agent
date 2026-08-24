import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from research_agent.schemas import (
    EvidenceBundle,
    ResearchExecutionResult,
    WorkerAssignment,
)
from research_agent.synthesis.aggregate import EvidenceAggregator
from research_agent.synthesis.base import (
    SynthesisEvidenceError,
    SynthesisProviderError,
    SynthesisTimeoutError,
)
from research_agent.synthesis.service import ResearchSynthesisService


def assignment(worker_id: str) -> WorkerAssignment:
    return WorkerAssignment(
        worker_id=worker_id,
        focused_task=f"Research {worker_id}",
        investigation_focus=f"Investigate {worker_id}",
        evidence_to_find=[f"Evidence for {worker_id}"],
    )


def successful_outcome(
    worker_id: str,
    *,
    claim: str,
    evidence: str,
    url: str,
    uncertainty: str | None = None,
) -> dict[str, Any]:
    worker_assignment = assignment(worker_id)
    return {
        "worker_id": worker_id,
        "assignment": worker_assignment,
        "status": "succeeded",
        "result": {
            "worker_id": worker_id,
            "assignment": worker_assignment,
            "claims": [
                {
                    "claim": claim,
                    "evidence": [{"source_id": "source-1", "evidence": evidence}],
                }
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "title": f"Source for {worker_id}",
                    "url": url,
                    "snippet": f"Context. {evidence} More context.",
                }
            ],
            "uncertainties": [uncertainty or f"Uncertainty from {worker_id}."],
        },
    }


def failed_outcome(worker_id: str) -> dict[str, Any]:
    return {
        "worker_id": worker_id,
        "assignment": assignment(worker_id),
        "status": "failed",
        "error": {"code": "timeout", "message": "worker execution timed out"},
    }


def execution(*outcomes: dict[str, Any]) -> ResearchExecutionResult:
    return ResearchExecutionResult(
        original_question="Is the approach effective?",
        objective="Assess effectiveness.",
        strategy="Compare independent evidence.",
        worker_count=len(outcomes),
        workers=list(outcomes),
    )


def standard_execution() -> ResearchExecutionResult:
    return execution(
        successful_outcome(
            "worker-1",
            claim="Production adoption increased",
            evidence="Survey reports increased adoption.",
            url="https://example.com/adoption",
        ),
        successful_outcome(
            "worker-2",
            claim="Production adoption increased in 2026",
            evidence="Case studies report production growth.",
            url="https://example.com/cases",
        ),
    )


def valid_draft(bundle: EvidenceBundle) -> dict[str, Any]:
    first_claim = bundle.claims[0]
    selection = {
        "claim_id": first_claim.claim_id,
        "evidence_ids": [first_claim.evidence[0].evidence_id],
    }
    return {
        "executive_summary": [selection.copy()],
        "key_findings": [selection.copy()],
        "important_claims": [selection.copy()],
        "conflicts": [],
        "uncertainties": [
            {
                "uncertainty_id": bundle.uncertainties[0].uncertainty_id,
            }
        ],
        "recommendations": [],
    }


class FakeSynthesizer:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.received: EvidenceBundle | None = None

    async def synthesize(self, evidence: EvidenceBundle) -> Any:
        self.received = evidence
        if self.error:
            raise self.error
        return self.result if self.result is not None else valid_draft(evidence)


def service(provider: FakeSynthesizer) -> ResearchSynthesisService:
    return ResearchSynthesisService(
        aggregator=EvidenceAggregator(),
        synthesizer=provider,
    )


def test_valid_synthesis_from_multiple_successful_workers() -> None:
    provider = FakeSynthesizer()

    report = asyncio.run(service(provider).synthesize(standard_execution()))

    assert report.original_question == "Is the approach effective?"
    assert len(report.sources) == 2
    assert provider.received is not None
    assert len(provider.received.claims) == 2


def test_duplicate_source_urls_preserve_provenance_and_snippets() -> None:
    research_execution = execution(
        successful_outcome(
            "worker-1",
            claim="Adoption increased",
            evidence="Survey reports growth.",
            url="https://example.com/shared",
        ),
        successful_outcome(
            "worker-2",
            claim="Adoption requires caution",
            evidence="Survey reports limitations.",
            url="https://example.com/shared",
        ),
    )

    bundle = EvidenceAggregator().aggregate(research_execution)

    assert len(bundle.sources) == 1
    assert len(bundle.sources[0].provenance) == 2
    assert len(bundle.sources[0].snippets) == 2
    assert len(bundle.sources[0].validated_excerpts) == 2


def test_exact_duplicate_claims_are_merged() -> None:
    research_execution = execution(
        successful_outcome(
            "worker-1",
            claim="Adoption increased",
            evidence="Survey reports growth.",
            url="https://example.com/one",
        ),
        successful_outcome(
            "worker-2",
            claim="  ADOPTION   INCREASED ",
            evidence="Case study reports growth.",
            url="https://example.com/two",
        ),
    )

    bundle = EvidenceAggregator().aggregate(research_execution)

    assert len(bundle.claims) == 1
    assert bundle.claims[0].worker_ids == ["worker-1", "worker-2"]
    assert len(bundle.claims[0].evidence) == 2


def test_obvious_overlapping_claims_are_flagged_without_merging() -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())

    assert len(bundle.claims) == 2
    assert bundle.overlapping_claims[0].claim_ids == ["claim-1", "claim-2"]


def test_conflicting_claims_are_preserved_in_report() -> None:
    research_execution = execution(
        successful_outcome(
            "worker-1",
            claim="The intervention improved outcomes.",
            evidence="Trial A reports improved outcomes.",
            url="https://example.com/a",
        ),
        successful_outcome(
            "worker-2",
            claim="The intervention did not improve outcomes.",
            evidence="Trial B reports no improvement.",
            url="https://example.com/b",
        ),
    )
    bundle = EvidenceAggregator().aggregate(research_execution)
    draft = valid_draft(bundle)
    draft["conflicts"] = [
        {
            "summary": "The trials report competing outcomes.",
            "positions": [
                    {
                        "claim_id": claim.claim_id,
                        "evidence_ids": [claim.evidence[0].evidence_id],
                }
                for claim in bundle.claims
            ],
        }
    ]

    report = asyncio.run(
        service(FakeSynthesizer(draft)).synthesize(research_execution)
    )

    assert len(report.conflicts) == 1
    assert len(report.conflicts[0].positions) == 2


def test_partial_worker_failure_is_injected_into_report() -> None:
    research_execution = execution(
        successful_outcome(
            "worker-1",
            claim="Adoption increased",
            evidence="Survey reports growth.",
            url="https://example.com/one",
        ),
        failed_outcome("worker-2"),
    )

    report = asyncio.run(
        service(FakeSynthesizer()).synthesize(research_execution)
    )

    assert report.failed_workers[0].worker_id == "worker-2"
    assert report.failed_workers[0].code == "timeout"


def test_unknown_claim_id_is_rejected() -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())
    draft = valid_draft(bundle)
    draft["key_findings"][0]["claim_id"] = "claim-unknown"

    with pytest.raises(SynthesisEvidenceError):
        asyncio.run(service(FakeSynthesizer(draft)).synthesize(standard_execution()))


def test_evidence_from_another_claim_is_rejected() -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())
    draft = valid_draft(bundle)
    draft["important_claims"][0]["evidence_ids"] = [
        bundle.claims[1].evidence[0].evidence_id
    ]

    with pytest.raises(SynthesisEvidenceError):
        asyncio.run(service(FakeSynthesizer(draft)).synthesize(standard_execution()))


def test_unknown_evidence_id_is_rejected_with_safe_diagnostic(caplog: Any) -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())
    draft = valid_draft(bundle)
    draft["important_claims"][0]["evidence_ids"] = ["evidence-unknown"]

    with pytest.raises(SynthesisEvidenceError):
        asyncio.run(service(FakeSynthesizer(draft)).synthesize(standard_execution()))

    record = next(item for item in caplog.records if item.message == "synthesis_validation_failed")
    assert record.validation_stage == "selection_resolution"
    assert record.field_path == "important_claims.0.evidence_ids"
    assert record.record_ids == ["<redacted-invalid-id>"]
    assert record.error_type == "unknown_evidence_id"
    assert "Survey reports increased adoption." not in caplog.text


@pytest.mark.parametrize(
    "unsafe_id",
    [
        "source contents must stay private",
        "credential-shaped-sensitive-value",
        "provider prompt fragment",
    ],
)
def test_unsafe_unknown_ids_are_redacted_from_diagnostics(
    caplog: Any,
    unsafe_id: str,
) -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())
    draft = valid_draft(bundle)
    draft["important_claims"][0]["evidence_ids"] = [unsafe_id]

    with pytest.raises(SynthesisEvidenceError):
        asyncio.run(service(FakeSynthesizer(draft)).synthesize(standard_execution()))

    assert unsafe_id not in caplog.text
    record = next(
        item for item in caplog.records if item.message == "synthesis_validation_failed"
    )
    assert record.record_ids == ["<redacted-invalid-id>"]


def test_provider_cannot_submit_factual_statement_text() -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())
    draft = valid_draft(bundle)
    draft["important_claims"][0]["statement"] = "An invented factual claim."

    with pytest.raises(SynthesisProviderError):
        asyncio.run(service(FakeSynthesizer(draft)).synthesize(standard_execution()))


def test_evidence_bundle_rejects_claim_with_unknown_source() -> None:
    data = EvidenceAggregator().aggregate(standard_execution()).model_dump()
    data["claims"][0]["evidence"][0]["source_id"] = "source-unknown"

    with pytest.raises(ValidationError, match="unknown source"):
        EvidenceBundle.model_validate(data)


def test_evidence_bundle_rejects_unvalidated_claim_evidence() -> None:
    data = EvidenceAggregator().aggregate(standard_execution()).model_dump()
    data["claims"][0]["evidence"][0]["evidence"] = "Unsupported evidence."

    with pytest.raises(ValidationError, match="unvalidated source evidence"):
        EvidenceBundle.model_validate(data)


def test_final_report_rejects_invalid_uncited_evidence_catalog_entry() -> None:
    research_execution = standard_execution()
    report = asyncio.run(service(FakeSynthesizer()).synthesize(research_execution))
    data = report.model_dump()
    data["evidence_claims"][1]["evidence"][0]["source_id"] = "source-unknown"

    with pytest.raises(ValidationError, match="unknown source"):
        type(report).model_validate(data)


def test_all_worker_failure_input_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one worker must succeed"):
        execution(failed_outcome("worker-1"), failed_outcome("worker-2"))


@pytest.mark.parametrize(
    "error",
    [SynthesisTimeoutError(), SynthesisProviderError()],
)
def test_synthesis_provider_errors_are_preserved(error: Exception) -> None:
    with pytest.raises(type(error)):
        asyncio.run(
            service(FakeSynthesizer(error=error)).synthesize(standard_execution())
        )


def test_malformed_structured_output_is_rejected() -> None:
    with pytest.raises(SynthesisProviderError, match="malformed structured output"):
        asyncio.run(
            service(FakeSynthesizer(result={"executive_summary": []})).synthesize(
                standard_execution()
            )
        )


def test_invented_uncertainty_is_rejected() -> None:
    bundle = EvidenceAggregator().aggregate(standard_execution())
    draft = valid_draft(bundle)
    draft["uncertainties"][0]["uncertainty_id"] = "uncertainty-unknown"

    with pytest.raises(SynthesisEvidenceError, match="unknown record"):
        asyncio.run(service(FakeSynthesizer(draft)).synthesize(standard_execution()))
