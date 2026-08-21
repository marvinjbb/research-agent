from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str

