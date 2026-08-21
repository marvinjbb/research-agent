from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str
