import pytest
from pydantic import ValidationError

from research_agent.schemas import ResearchDepth, ResearchRequest


def test_research_request_uses_safe_defaults_and_normalizes_question() -> None:
    request = ResearchRequest(question="  What changed in battery recycling?  ")

    assert request.question == "What changed in battery recycling?"
    assert request.depth is ResearchDepth.QUICK


@pytest.mark.parametrize("question", ["", "   "])
def test_research_request_rejects_blank_question(question: str) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(question=question)


def test_research_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(question="A valid question", worker_count=10)
