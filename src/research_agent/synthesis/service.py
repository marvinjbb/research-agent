from pydantic import ValidationError

from research_agent.schemas import (
    EvidenceBundle,
    FinalResearchReport,
    ResearchExecutionResult,
    SynthesisDraft,
)
from research_agent.synthesis.aggregate import EvidenceAggregator
from research_agent.synthesis.base import (
    ResearchSynthesizer,
    SynthesisEvidenceError,
    SynthesisProviderError,
)


class ResearchSynthesisService:
    """Aggregate evidence, call synthesis, and enforce final grounding."""

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
            draft = SynthesisDraft.model_validate(
                await self._synthesizer.synthesize(evidence)
            )
        except ValidationError as exc:
            raise SynthesisProviderError(
                "synthesis provider returned malformed structured output"
            ) from exc
        self._validate_uncertainties(draft, evidence)
        try:
            return FinalResearchReport(
                original_question=evidence.original_question,
                objective=evidence.objective,
                strategy=evidence.strategy,
                executive_summary=draft.executive_summary,
                key_findings=draft.key_findings,
                important_claims=draft.important_claims,
                conflicts=draft.conflicts,
                uncertainties=draft.uncertainties,
                recommendations=draft.recommendations,
                evidence_claims=evidence.claims,
                sources=evidence.sources,
                failed_workers=evidence.failed_workers,
            )
        except ValidationError as exc:
            raise SynthesisEvidenceError(
                "synthesis contains unsupported claims or citations"
            ) from exc

    def _validate_uncertainties(
        self,
        draft: SynthesisDraft,
        evidence: EvidenceBundle,
    ) -> None:
        known = {
            (uncertainty.worker_id, uncertainty.statement)
            for uncertainty in evidence.uncertainties
        }
        for uncertainty in draft.uncertainties:
            if any(
                (worker_id, uncertainty.statement) not in known
                for worker_id in uncertainty.worker_ids
            ):
                raise SynthesisEvidenceError(
                    "synthesis uncertainty was not supplied by its referenced worker"
                )
