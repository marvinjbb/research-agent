from hashlib import sha256
from typing import Any

from research_agent.schemas import (
    AggregatedClaim,
    AggregatedEvidence,
    AggregatedSource,
    AggregatedUncertainty,
    ClaimOverlap,
    EvidenceBundle,
    FailedWorkerSummary,
    ResearchExecutionResult,
    SourceProvenance,
    WorkerExecutionStatus,
)
from research_agent.synthesis.base import NoSuccessfulWorkersError


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


class EvidenceAggregator:
    """Deterministically aggregate already-validated worker evidence."""

    def aggregate(self, execution: ResearchExecutionResult) -> EvidenceBundle:
        successful = [
            outcome
            for outcome in execution.workers
            if outcome.status is WorkerExecutionStatus.SUCCEEDED
            and outcome.result is not None
        ]
        if not successful:
            raise NoSuccessfulWorkersError("no successful worker evidence")

        sources_by_url: dict[str, dict[str, Any]] = {}
        source_id_map: dict[tuple[str, str], str] = {}
        for outcome in successful:
            result = outcome.result
            assert result is not None
            excerpts_by_source: dict[str, list[str]] = {}
            for claim in result.claims:
                for evidence in claim.evidence:
                    excerpts_by_source.setdefault(evidence.source_id, []).append(
                        evidence.evidence
                    )

            for source in result.sources:
                url = str(source.url)
                source_data = sources_by_url.get(url)
                if source_data is None:
                    source_data = {
                        "source_id": f"source-{len(sources_by_url) + 1}",
                        "title": source.title,
                        "url": url,
                        "snippets": [],
                        "validated_excerpts": [],
                        "provenance": [],
                        "publisher": source.publisher,
                    }
                    sources_by_url[url] = source_data
                if source.snippet not in source_data["snippets"]:
                    source_data["snippets"].append(source.snippet)
                for excerpt in excerpts_by_source.get(source.source_id, []):
                    if excerpt not in source_data["validated_excerpts"]:
                        source_data["validated_excerpts"].append(excerpt)
                source_data["provenance"].append(
                    SourceProvenance(
                        worker_id=result.worker_id,
                        worker_source_id=source.source_id,
                    )
                )
                source_id_map[(result.worker_id, source.source_id)] = source_data[
                    "source_id"
                ]

        sources = [
            AggregatedSource.model_validate(source) for source in sources_by_url.values()
        ]
        claims_by_text: dict[str, dict[str, Any]] = {}
        for outcome in successful:
            result = outcome.result
            assert result is not None
            for claim in result.claims:
                normalized = _normalized_text(claim.claim)
                claim_data = claims_by_text.get(normalized)
                if claim_data is None:
                    claim_data = {
                        "claim_id": f"claim-{len(claims_by_text) + 1}",
                        "statement": claim.claim,
                        "evidence": [],
                        "worker_ids": [],
                    }
                    claims_by_text[normalized] = claim_data
                if result.worker_id not in claim_data["worker_ids"]:
                    claim_data["worker_ids"].append(result.worker_id)
                for evidence in claim.evidence:
                    aggregated = AggregatedEvidence(
                        evidence_id=str(evidence.evidence_id),
                        source_id=source_id_map[
                            (result.worker_id, evidence.source_id)
                        ],
                        evidence=evidence.evidence,
                    )
                    if aggregated not in claim_data["evidence"]:
                        claim_data["evidence"].append(aggregated)

        claims = [
            AggregatedClaim.model_validate(claim) for claim in claims_by_text.values()
        ]
        overlaps = self._find_obvious_overlaps(claims)
        uncertainties = [
            AggregatedUncertainty(
                uncertainty_id=(
                    "uncertainty-"
                    + sha256(
                        f"{outcome.worker_id}\0{uncertainty}".encode()
                    ).hexdigest()[:28]
                ),
                worker_id=outcome.worker_id,
                statement=uncertainty,
            )
            for outcome in successful
            for uncertainty in outcome.result.uncertainties
            if outcome.result is not None
        ]
        failed_workers = [
            FailedWorkerSummary(
                worker_id=outcome.worker_id,
                assignment=outcome.assignment,
                code=outcome.error.code,
                message=outcome.error.message,
            )
            for outcome in execution.workers
            if outcome.status is WorkerExecutionStatus.FAILED
            and outcome.error is not None
        ]
        return EvidenceBundle(
            original_question=execution.original_question,
            objective=execution.objective,
            strategy=execution.strategy,
            sources=sources,
            claims=claims,
            overlapping_claims=overlaps,
            uncertainties=uncertainties,
            failed_workers=failed_workers,
        )

    def _find_obvious_overlaps(
        self,
        claims: list[AggregatedClaim],
    ) -> list[ClaimOverlap]:
        overlaps: list[ClaimOverlap] = []
        for index, left in enumerate(claims):
            left_text = _normalized_text(left.statement)
            for right in claims[index + 1 :]:
                right_text = _normalized_text(right.statement)
                if left_text in right_text or right_text in left_text:
                    overlaps.append(
                        ClaimOverlap(claim_ids=[left.claim_id, right.claim_id])
                    )
        return overlaps
