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


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str
