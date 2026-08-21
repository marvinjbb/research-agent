import pytest
from pydantic import ValidationError

from research_agent.schemas import ResearchPlan


def assignment(worker_id: str, task: str) -> dict[str, object]:
    return {
        "worker_id": worker_id,
        "focused_task": task,
        "investigation_focus": f"Investigate {task}",
        "evidence_to_find": ["Credible evidence"],
    }


def plan_with(assignments: list[dict[str, object]]) -> ResearchPlan:
    return ResearchPlan(
        original_question="Is RAG still important for production AI systems?",
        objective="Assess when RAG remains useful.",
        strategy="Compare use cases, limitations, and alternatives.",
        worker_count=len(assignments),
        assignments=assignments,
    )


def test_valid_two_worker_plan() -> None:
    plan = plan_with(
        [assignment("worker-1", "RAG use cases"), assignment("worker-2", "Alternatives")]
    )

    assert plan.worker_count == 2


def test_valid_five_worker_plan() -> None:
    assignments = [assignment(f"worker-{number}", f"Area {number}") for number in range(1, 6)]

    assert plan_with(assignments).worker_count == 5


@pytest.mark.parametrize("count", [1, 6])
def test_worker_count_outside_bounds_is_rejected(count: int) -> None:
    assignments = [assignment(f"worker-{number}", f"Area {number}") for number in range(count)]

    with pytest.raises(ValidationError):
        plan_with(assignments)


def test_duplicate_worker_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="worker IDs must be unique"):
        plan_with([assignment("worker-1", "Use cases"), assignment("worker-1", "Risks")])


@pytest.mark.parametrize("field", ["focused_task", "investigation_focus"])
def test_blank_assignment_text_is_rejected(field: str) -> None:
    invalid = assignment("worker-1", "Use cases")
    invalid[field] = "   "

    with pytest.raises(ValidationError):
        plan_with([invalid, assignment("worker-2", "Alternatives")])


def test_blank_evidence_requirement_is_rejected() -> None:
    invalid = assignment("worker-1", "Use cases")
    invalid["evidence_to_find"] = ["   "]

    with pytest.raises(ValidationError):
        plan_with([invalid, assignment("worker-2", "Alternatives")])
