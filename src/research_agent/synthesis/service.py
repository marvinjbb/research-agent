import logging
import re
from collections.abc import Iterable

from pydantic import ValidationError

from research_agent.schemas import (
    AggregatedClaim,
    AggregatedEvidence,
    AggregatedUncertainty,
    CitedReportClaim,
    EvidenceBundle,
    FinalResearchReport,
    ReportCitation,
    ReportConflict,
    ReportRecommendation,
    ReportUncertainty,
    ResearchExecutionResult,
    SynthesisClaimSelection,
    SynthesisDraft,
    SynthesisRecommendationSelection,
)
from research_agent.synthesis.aggregate import EvidenceAggregator
from research_agent.synthesis.base import (
    ResearchSynthesizer,
    SynthesisEvidenceError,
    SynthesisProviderError,
)

logger = logging.getLogger(__name__)
SAFE_RECORD_ID = re.compile(r"(?:claim-[1-9][0-9]*|evidence-[0-9a-f]{32}|uncertainty-[0-9a-f]{28})")


class ResearchSynthesisService:
    """Aggregate evidence, resolve provider selections, and validate the report."""

    def __init__(
        self,
        *,
        aggregator: EvidenceAggregator,
        synthesizer: ResearchSynthesizer,
    ) -> None:
        self._aggregator = aggregator
        self._synthesizer = synthesizer

    async def synthesize(
        self,
        execution: ResearchExecutionResult,
    ) -> FinalResearchReport:
        evidence = self._aggregator.aggregate(execution)
        try:
            draft = SynthesisDraft.model_validate(await self._synthesizer.synthesize(evidence))
        except ValidationError as exc:
            self._log_pydantic_failure("provider_schema", exc)
            raise SynthesisProviderError(
                "synthesis provider returned malformed structured output"
            ) from exc

        try:
            report_parts = self._resolve_draft(draft, evidence)
            return FinalResearchReport(
                original_question=evidence.original_question,
                objective=evidence.objective,
                strategy=evidence.strategy,
                **report_parts,
                evidence_claims=evidence.claims,
                sources=evidence.sources,
                failed_workers=evidence.failed_workers,
            )
        except SynthesisEvidenceError:
            raise
        except ValidationError as exc:
            self._log_pydantic_failure("final_report", exc)
            raise SynthesisEvidenceError(
                "synthesis contains unsupported claims or citations"
            ) from exc

    def _resolve_draft(
        self,
        draft: SynthesisDraft,
        evidence: EvidenceBundle,
    ) -> dict[str, object]:
        claims = {claim.claim_id: claim for claim in evidence.claims}
        uncertainties = {
            uncertainty.uncertainty_id: uncertainty for uncertainty in evidence.uncertainties
        }
        return {
            "executive_summary": self._resolve_claims(
                draft.executive_summary, claims, "executive_summary"
            ),
            "key_findings": self._resolve_claims(draft.key_findings, claims, "key_findings"),
            "important_claims": self._resolve_claims(
                draft.important_claims, claims, "important_claims"
            ),
            "conflicts": [
                ReportConflict(
                    summary=conflict.summary,
                    positions=self._resolve_claims(
                        conflict.positions, claims, f"conflicts.{index}.positions"
                    ),
                )
                for index, conflict in enumerate(draft.conflicts)
            ],
            "uncertainties": [
                self._resolve_uncertainty(
                    selection.uncertainty_id,
                    uncertainties,
                    f"uncertainties.{index}.uncertainty_id",
                )
                for index, selection in enumerate(draft.uncertainties)
            ],
            "recommendations": [
                self._resolve_recommendation(item, claims, index)
                for index, item in enumerate(draft.recommendations)
            ],
        }

    def _resolve_claims(
        self,
        selections: Iterable[SynthesisClaimSelection],
        claims: dict[str, AggregatedClaim],
        field: str,
    ) -> list[CitedReportClaim]:
        return [
            self._resolve_claim(selection, claims, f"{field}.{index}")
            for index, selection in enumerate(selections)
        ]

    def _resolve_claim(
        self,
        selection: SynthesisClaimSelection,
        claims: dict[str, AggregatedClaim],
        field: str,
    ) -> CitedReportClaim:
        claim = self._known_claim(selection.claim_id, claims, f"{field}.claim_id")
        citations = self._resolve_evidence_ids(
            selection.evidence_ids,
            [claim],
            f"{field}.evidence_ids",
        )
        return CitedReportClaim(
            statement=claim.statement,
            claim_ids=[claim.claim_id],
            citations=citations,
        )

    def _resolve_uncertainty(
        self,
        uncertainty_id: str,
        uncertainties: dict[str, AggregatedUncertainty],
        field: str,
    ) -> ReportUncertainty:
        uncertainty = uncertainties.get(uncertainty_id)
        if uncertainty is None:
            self._raise_unknown("unknown_uncertainty_id", field, [uncertainty_id])
        assert uncertainty is not None
        return ReportUncertainty(
            statement=uncertainty.statement,
            worker_ids=[uncertainty.worker_id],
        )

    def _resolve_recommendation(
        self,
        selection: SynthesisRecommendationSelection,
        claims: dict[str, AggregatedClaim],
        index: int,
    ) -> ReportRecommendation:
        selected_claims = [
            self._known_claim(claim_id, claims, f"recommendations.{index}.claim_ids")
            for claim_id in selection.claim_ids
        ]
        citations = self._resolve_evidence_ids(
            selection.evidence_ids,
            selected_claims,
            f"recommendations.{index}.evidence_ids",
        )
        return ReportRecommendation(
            guidance=selection.guidance,
            rationale=selection.rationale,
            citations=citations,
        )

    def _resolve_evidence_ids(
        self,
        evidence_ids: list[str],
        claims: list[AggregatedClaim],
        field: str,
    ) -> list[ReportCitation]:
        known = {str(item.evidence_id): item for claim in claims for item in claim.evidence}
        citations: list[ReportCitation] = []
        for evidence_id in evidence_ids:
            item = known.get(evidence_id)
            if item is None:
                self._raise_unknown("unknown_evidence_id", field, [evidence_id])
            assert isinstance(item, AggregatedEvidence)
            citations.append(
                ReportCitation(
                    evidence_id=item.evidence_id,
                    source_id=item.source_id,
                    evidence=item.evidence,
                )
            )
        return citations

    def _known_claim(
        self,
        claim_id: str,
        claims: dict[str, AggregatedClaim],
        field: str,
    ) -> AggregatedClaim:
        claim = claims.get(claim_id)
        if claim is None:
            self._raise_unknown("unknown_claim_id", field, [claim_id])
        assert claim is not None
        return claim

    @staticmethod
    def _raise_unknown(error_type: str, field: str, record_ids: list[str]) -> None:
        logger.warning(
            "synthesis_validation_failed",
            extra={
                "validation_stage": "selection_resolution",
                "field_path": field,
                "record_ids": [
                    record_id if SAFE_RECORD_ID.fullmatch(record_id) else "<redacted-invalid-id>"
                    for record_id in record_ids
                ],
                "error_type": error_type,
            },
        )
        raise SynthesisEvidenceError("synthesis selection references an unknown record")

    @staticmethod
    def _log_pydantic_failure(stage: str, error: ValidationError) -> None:
        for item in error.errors(include_input=False, include_context=False):
            logger.warning(
                "synthesis_validation_failed",
                extra={
                    "validation_stage": stage,
                    "field_path": ".".join(str(part) for part in item["loc"]),
                    "record_ids": [],
                    "error_type": item["type"],
                },
            )
