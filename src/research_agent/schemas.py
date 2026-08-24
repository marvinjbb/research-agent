from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResearchDepth(StrEnum):
    """Supported research effort levels for the initial API contract."""

    QUICK = "quick"
    DEEP = "deep"


class ResearchRequest(BaseModel):
    """Input accepted by a future research endpoint."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)
    depth: ResearchDepth = ResearchDepth.QUICK

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("question must not be blank")
        return question


class WorkerAssignment(BaseModel):
    """One focused, non-executing research assignment in a plan."""

    model_config = ConfigDict(extra="forbid")

    worker_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    focused_task: Annotated[NonBlankText, StringConstraints(max_length=500)]
    investigation_focus: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    evidence_to_find: list[
        Annotated[NonBlankText, StringConstraints(max_length=300)]
    ] = Field(min_length=1, max_length=8)


class ResearchPlan(BaseModel):
    """Validated output from the planning layer; it does not execute workers."""

    model_config = ConfigDict(extra="forbid")

    original_question: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    objective: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    strategy: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    worker_count: int = Field(ge=2, le=5)
    assignments: list[WorkerAssignment] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def validate_assignments(self) -> "ResearchPlan":
        if self.worker_count != len(self.assignments):
            raise ValueError("worker_count must equal the number of assignments")

        worker_ids = [assignment.worker_id for assignment in self.assignments]
        if len(worker_ids) != len(set(worker_ids)):
            raise ValueError("worker IDs must be unique")

        normalized_tasks = [
            " ".join(assignment.focused_task.casefold().split())
            for assignment in self.assignments
        ]
        if len(normalized_tasks) != len(set(normalized_tasks)):
            raise ValueError("focused research tasks must be unique")

        return self


class SearchSource(BaseModel):
    """Normalized source returned by an application-owned search provider."""

    model_config = ConfigDict(extra="forbid")

    source_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    title: Annotated[NonBlankText, StringConstraints(max_length=500)]
    url: HttpUrl
    snippet: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    publisher: Annotated[NonBlankText, StringConstraints(max_length=300)] | None = None


class ClaimEvidence(BaseModel):
    """A traceable piece of source evidence supporting one claim."""

    model_config = ConfigDict(extra="forbid")

    source_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    evidence: Annotated[NonBlankText, StringConstraints(max_length=1_000)]

    @field_validator("evidence", mode="before")
    @classmethod
    def remove_matching_outer_quotes(cls, value: object) -> object:
        if not isinstance(value, str) or len(value) < 2:
            return value

        matching_quotes = {'"': '"', "'": "'", "“": "”", "‘": "’"}
        if matching_quotes.get(value[0]) == value[-1]:
            return value[1:-1]
        return value


class WorkerClaim(BaseModel):
    """A factual finding that must include at least one source reference."""

    model_config = ConfigDict(extra="forbid")

    claim: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    evidence: list[ClaimEvidence] = Field(min_length=1, max_length=8)


class WorkerAnalysis(BaseModel):
    """Structured LLM analysis built only from supplied search sources."""

    model_config = ConfigDict(extra="forbid")

    claims: list[WorkerClaim] = Field(min_length=1, max_length=12)
    uncertainties: list[
        Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    ] = Field(min_length=1, max_length=8)


class WorkerResult(BaseModel):
    """Validated result for exactly one research worker assignment."""

    model_config = ConfigDict(extra="forbid")

    worker_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    assignment: WorkerAssignment
    claims: list[WorkerClaim] = Field(min_length=1, max_length=12)
    sources: list[SearchSource] = Field(min_length=1, max_length=10)
    uncertainties: list[
        Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    ] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_source_grounding(self) -> "WorkerResult":
        if self.worker_id != self.assignment.worker_id:
            raise ValueError("worker_id must match assignment.worker_id")

        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source IDs must be unique")

        source_urls = [str(source.url) for source in self.sources]
        if len(source_urls) != len(set(source_urls)):
            raise ValueError("source URLs must be unique")

        sources_by_id = {source.source_id: source for source in self.sources}
        known_source_ids = set(sources_by_id)
        cited_source_ids = {
            evidence.source_id
            for claim in self.claims
            for evidence in claim.evidence
        }
        unknown_source_ids = cited_source_ids - known_source_ids
        if unknown_source_ids:
            unknown = ", ".join(sorted(unknown_source_ids))
            raise ValueError(f"evidence references unknown sources: {unknown}")

        for claim in self.claims:
            for evidence in claim.evidence:
                source_text = sources_by_id[evidence.source_id].snippet
                if evidence.evidence not in source_text:
                    raise ValueError(
                        "claim evidence must be an excerpt from the referenced source"
                    )

        return self


class WorkerExecutionStatus(StrEnum):
    """Outcome states for one planned worker execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkerFailure(BaseModel):
    """Safe application-owned metadata for one failed worker."""

    model_config = ConfigDict(extra="forbid")

    code: Annotated[NonBlankText, StringConstraints(max_length=50)]
    message: Annotated[NonBlankText, StringConstraints(max_length=300)]


class WorkerExecutionOutcome(BaseModel):
    """Ordered success or failure for one plan assignment."""

    model_config = ConfigDict(extra="forbid")

    worker_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    assignment: WorkerAssignment
    status: WorkerExecutionStatus
    result: WorkerResult | None = None
    error: WorkerFailure | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "WorkerExecutionOutcome":
        if self.worker_id != self.assignment.worker_id:
            raise ValueError("worker_id must match assignment.worker_id")
        if self.status is WorkerExecutionStatus.SUCCEEDED:
            if self.result is None or self.error is not None:
                raise ValueError("successful outcome requires only a worker result")
            if self.result.worker_id != self.worker_id:
                raise ValueError("result worker_id must match outcome worker_id")
            if self.result.assignment != self.assignment:
                raise ValueError("result assignment must match outcome assignment")
        elif self.result is not None or self.error is None:
            raise ValueError("failed outcome requires only worker error metadata")
        return self


class ResearchExecutionResult(BaseModel):
    """Ordered outcomes from executing one validated research plan."""

    model_config = ConfigDict(extra="forbid")

    original_question: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    objective: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    strategy: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    worker_count: int = Field(ge=2, le=5)
    workers: list[WorkerExecutionOutcome] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def validate_execution(self) -> "ResearchExecutionResult":
        if self.worker_count != len(self.workers):
            raise ValueError("worker_count must equal the number of worker outcomes")
        worker_ids = [worker.worker_id for worker in self.workers]
        if len(worker_ids) != len(set(worker_ids)):
            raise ValueError("worker outcome IDs must be unique")
        if not any(
            worker.status is WorkerExecutionStatus.SUCCEEDED
            for worker in self.workers
        ):
            raise ValueError("at least one worker must succeed")
        return self


class SourceProvenance(BaseModel):
    """Original worker source identity retained after URL deduplication."""

    model_config = ConfigDict(extra="forbid")

    worker_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    worker_source_id: Annotated[NonBlankText, StringConstraints(max_length=50)]


class AggregatedSource(BaseModel):
    """One URL with validated excerpts and worker provenance preserved."""

    model_config = ConfigDict(extra="forbid")

    source_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    title: Annotated[NonBlankText, StringConstraints(max_length=500)]
    url: HttpUrl
    snippets: list[Annotated[NonBlankText, StringConstraints(max_length=2_000)]] = Field(
        min_length=1,
        max_length=5,
    )
    validated_excerpts: list[
        Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    ] = Field(default_factory=list, max_length=480)
    provenance: list[SourceProvenance] = Field(min_length=1, max_length=5)
    publisher: Annotated[NonBlankText, StringConstraints(max_length=300)] | None = None

    @model_validator(mode="after")
    def validate_aggregated_source(self) -> "AggregatedSource":
        if len(self.snippets) != len(set(self.snippets)):
            raise ValueError("aggregated source snippets must be unique")
        if len(self.validated_excerpts) != len(set(self.validated_excerpts)):
            raise ValueError("validated source excerpts must be unique")
        provenance_keys = {
            (item.worker_id, item.worker_source_id) for item in self.provenance
        }
        if len(provenance_keys) != len(self.provenance):
            raise ValueError("source provenance records must be unique")
        if any(
            not any(excerpt in snippet for snippet in self.snippets)
            for excerpt in self.validated_excerpts
        ):
            raise ValueError("validated excerpts must occur in a source snippet")
        return self


class AggregatedEvidence(BaseModel):
    """Validated worker evidence remapped to an aggregated source."""

    model_config = ConfigDict(extra="forbid")

    source_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    evidence: Annotated[NonBlankText, StringConstraints(max_length=1_000)]


class AggregatedClaim(BaseModel):
    """An exact-deduplicated worker claim with combined provenance."""

    model_config = ConfigDict(extra="forbid")

    claim_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    statement: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    evidence: list[AggregatedEvidence] = Field(min_length=1, max_length=40)
    worker_ids: list[
        Annotated[NonBlankText, StringConstraints(max_length=50)]
    ] = Field(min_length=1, max_length=5)


class ClaimOverlap(BaseModel):
    """Claims with deterministic exact-text containment overlap."""

    model_config = ConfigDict(extra="forbid")

    claim_ids: list[
        Annotated[NonBlankText, StringConstraints(max_length=50)]
    ] = Field(min_length=2, max_length=12)


class AggregatedUncertainty(BaseModel):
    """One worker uncertainty preserved without model rewriting."""

    model_config = ConfigDict(extra="forbid")

    worker_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    statement: Annotated[NonBlankText, StringConstraints(max_length=1_000)]


class FailedWorkerSummary(BaseModel):
    """Safe failed-worker metadata carried into the final report."""

    model_config = ConfigDict(extra="forbid")

    worker_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    assignment: WorkerAssignment
    code: Annotated[NonBlankText, StringConstraints(max_length=50)]
    message: Annotated[NonBlankText, StringConstraints(max_length=300)]


def _validate_claim_catalog(
    sources: list[AggregatedSource],
    claims: list[AggregatedClaim],
) -> None:
    sources_by_id = {source.source_id: source for source in sources}
    if len(sources_by_id) != len(sources):
        raise ValueError("aggregated source IDs must be unique")
    source_urls = [str(source.url) for source in sources]
    if len(source_urls) != len(set(source_urls)):
        raise ValueError("aggregated source URLs must be unique")

    claim_ids = [claim.claim_id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("aggregated claim IDs must be unique")
    for claim in claims:
        for evidence in claim.evidence:
            source = sources_by_id.get(evidence.source_id)
            if source is None:
                raise ValueError("aggregated claim references an unknown source")
            if evidence.evidence not in source.validated_excerpts:
                raise ValueError("aggregated claim uses unvalidated source evidence")


class EvidenceBundle(BaseModel):
    """Deterministic provider input derived from validated worker outcomes."""

    model_config = ConfigDict(extra="forbid")

    original_question: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    objective: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    strategy: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    sources: list[AggregatedSource] = Field(min_length=1, max_length=50)
    claims: list[AggregatedClaim] = Field(min_length=1, max_length=60)
    overlapping_claims: list[ClaimOverlap] = Field(default_factory=list)
    uncertainties: list[AggregatedUncertainty] = Field(default_factory=list)
    failed_workers: list[FailedWorkerSummary] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_bundle_grounding(self) -> "EvidenceBundle":
        _validate_claim_catalog(self.sources, self.claims)
        known_claim_ids = {claim.claim_id for claim in self.claims}
        if any(
            claim_id not in known_claim_ids
            for overlap in self.overlapping_claims
            for claim_id in overlap.claim_ids
        ):
            raise ValueError("claim overlap references an unknown claim")
        return self


class ReportCitation(BaseModel):
    """Citation to evidence already validated by a successful worker."""

    model_config = ConfigDict(extra="forbid")

    source_id: Annotated[NonBlankText, StringConstraints(max_length=50)]
    evidence: Annotated[NonBlankText, StringConstraints(max_length=1_000)]


class CitedReportClaim(BaseModel):
    """Evidence-backed factual statement in the final report."""

    model_config = ConfigDict(extra="forbid")

    statement: Annotated[NonBlankText, StringConstraints(max_length=1_500)]
    claim_ids: list[
        Annotated[NonBlankText, StringConstraints(max_length=50)]
    ] = Field(min_length=1, max_length=10)
    citations: list[ReportCitation] = Field(min_length=1, max_length=10)


class ReportConflict(BaseModel):
    """Competing evidence presented without silently choosing a side."""

    model_config = ConfigDict(extra="forbid")

    summary: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    positions: list[CitedReportClaim] = Field(min_length=2, max_length=6)


class ReportUncertainty(BaseModel):
    """Limitation attributed to successful worker output."""

    model_config = ConfigDict(extra="forbid")

    statement: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    worker_ids: list[
        Annotated[NonBlankText, StringConstraints(max_length=50)]
    ] = Field(min_length=1, max_length=5)


class ReportRecommendation(BaseModel):
    """Decision guidance explicitly separated from factual findings."""

    model_config = ConfigDict(extra="forbid")

    guidance: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    rationale: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    citations: list[ReportCitation] = Field(min_length=1, max_length=10)


class SynthesisDraft(BaseModel):
    """Structured provider output before deterministic report assembly."""

    model_config = ConfigDict(extra="forbid")

    executive_summary: list[CitedReportClaim] = Field(min_length=1, max_length=5)
    key_findings: list[CitedReportClaim] = Field(min_length=1, max_length=12)
    important_claims: list[CitedReportClaim] = Field(min_length=1, max_length=20)
    conflicts: list[ReportConflict] = Field(default_factory=list, max_length=8)
    uncertainties: list[ReportUncertainty] = Field(default_factory=list, max_length=12)
    recommendations: list[ReportRecommendation] = Field(default_factory=list, max_length=8)


class FinalResearchReport(BaseModel):
    """Application-owned, source-grounded final report contract."""

    model_config = ConfigDict(extra="forbid")

    original_question: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    objective: Annotated[NonBlankText, StringConstraints(max_length=1_000)]
    strategy: Annotated[NonBlankText, StringConstraints(max_length=2_000)]
    executive_summary: list[CitedReportClaim] = Field(min_length=1, max_length=5)
    key_findings: list[CitedReportClaim] = Field(min_length=1, max_length=12)
    important_claims: list[CitedReportClaim] = Field(min_length=1, max_length=20)
    conflicts: list[ReportConflict] = Field(default_factory=list, max_length=8)
    uncertainties: list[ReportUncertainty] = Field(default_factory=list, max_length=12)
    recommendations: list[ReportRecommendation] = Field(default_factory=list, max_length=8)
    evidence_claims: list[AggregatedClaim] = Field(min_length=1, max_length=60)
    sources: list[AggregatedSource] = Field(min_length=1, max_length=50)
    failed_workers: list[FailedWorkerSummary] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_report_grounding(self) -> "FinalResearchReport":
        _validate_claim_catalog(self.sources, self.evidence_claims)
        sources_by_id = {source.source_id: source for source in self.sources}
        evidence_claims_by_id = {
            claim.claim_id: claim for claim in self.evidence_claims
        }
        claims = [
            *self.executive_summary,
            *self.key_findings,
            *self.important_claims,
            *(position for conflict in self.conflicts for position in conflict.positions),
        ]
        for claim in claims:
            referenced_claims = [
                evidence_claims_by_id.get(claim_id) for claim_id in claim.claim_ids
            ]
            if any(item is None for item in referenced_claims):
                raise ValueError("report statement references an unknown claim")
            known_claims = [item for item in referenced_claims if item is not None]
            if claim.statement not in {item.statement for item in known_claims}:
                raise ValueError("report statement is not a validated worker claim")
            allowed_evidence = {
                (evidence.source_id, evidence.evidence)
                for item in known_claims
                for evidence in item.evidence
            }
            if any(
                (citation.source_id, citation.evidence) not in allowed_evidence
                for citation in claim.citations
            ):
                raise ValueError("report claim cites unrelated worker evidence")
        citations = [
            *(citation for claim in claims for citation in claim.citations),
            *(
                citation
                for recommendation in self.recommendations
                for citation in recommendation.citations
            ),
        ]
        for citation in citations:
            source = sources_by_id.get(citation.source_id)
            if source is None:
                raise ValueError("report citation references an unknown source")
            if citation.evidence not in source.validated_excerpts:
                raise ValueError("report citation is not validated worker evidence")

        successful_worker_ids = {
            provenance.worker_id
            for source in self.sources
            for provenance in source.provenance
        }
        for uncertainty in self.uncertainties:
            if not set(uncertainty.worker_ids) <= successful_worker_ids:
                raise ValueError("uncertainty references an unknown successful worker")

        failed_worker_ids = [worker.worker_id for worker in self.failed_workers]
        if len(failed_worker_ids) != len(set(failed_worker_ids)):
            raise ValueError("failed worker summaries must be unique")
        if set(failed_worker_ids) & successful_worker_ids:
            raise ValueError("a worker cannot be both successful and failed")
        return self


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str
