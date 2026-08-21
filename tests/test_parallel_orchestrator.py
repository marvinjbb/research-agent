import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from research_agent.orchestration.parallel import (
    AllWorkersFailedError,
    ParallelResearchOrchestrator,
)
from research_agent.schemas import (
    ResearchExecutionResult,
    ResearchPlan,
    WorkerAssignment,
    WorkerExecutionStatus,
    WorkerResult,
)
from research_agent.workers.base import WorkerProviderError, WorkerTimeoutError


def plan(worker_count: int) -> ResearchPlan:
    return ResearchPlan(
        original_question="How is this technology used?",
        objective="Assess current use.",
        strategy="Divide the evidence into focused areas.",
        worker_count=worker_count,
        assignments=[
            WorkerAssignment(
                worker_id=f"worker-{index}",
                focused_task=f"Research area {index}",
                investigation_focus=f"Investigate evidence area {index}",
                evidence_to_find=[f"Evidence type {index}"],
            )
            for index in range(1, worker_count + 1)
        ],
    )


def result_for(assignment: WorkerAssignment) -> WorkerResult:
    evidence = f"Grounded evidence for {assignment.worker_id}."
    return WorkerResult.model_validate(
        {
            "worker_id": assignment.worker_id,
            "assignment": assignment,
            "claims": [
                {
                    "claim": f"Grounded claim for {assignment.worker_id}.",
                    "evidence": [{"source_id": "source-1", "evidence": evidence}],
                }
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "title": "Evidence report",
                    "url": f"https://example.com/{assignment.worker_id}",
                    "snippet": evidence,
                }
            ],
            "uncertainties": ["Evidence scope is limited."],
        }
    )


class FakeWorker:
    def __init__(
        self,
        behavior: Callable[[WorkerAssignment], Any],
    ) -> None:
        self._behavior = behavior

    async def research(self, assignment: WorkerAssignment) -> Any:
        outcome = self._behavior(assignment)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, tuple):
            delay, value, completed = outcome
            await asyncio.sleep(delay)
            completed.append(assignment.worker_id)
            return value
        return outcome


def orchestrator(
    behavior: Callable[[WorkerAssignment], Any],
) -> ParallelResearchOrchestrator:
    return ParallelResearchOrchestrator(
        worker_factory=lambda: FakeWorker(behavior),
    )


@pytest.mark.parametrize("worker_count", [2, 5])
def test_executes_every_bounded_worker(worker_count: int) -> None:
    research_plan = plan(worker_count)

    execution = asyncio.run(
        orchestrator(result_for).execute(research_plan)
    )

    assert len(execution.workers) == worker_count
    assert all(
        outcome.status is WorkerExecutionStatus.SUCCEEDED
        for outcome in execution.workers
    )


def test_completion_order_does_not_change_assignment_order() -> None:
    research_plan = plan(2)
    completed: list[str] = []
    delays = {"worker-1": 0.02, "worker-2": 0.0}

    execution = asyncio.run(
        orchestrator(
            lambda assignment: (
                delays[assignment.worker_id],
                result_for(assignment),
                completed,
            )
        ).execute(research_plan)
    )

    assert completed == ["worker-2", "worker-1"]
    assert [worker.worker_id for worker in execution.workers] == [
        "worker-1",
        "worker-2",
    ]


def test_one_failure_returns_remaining_successes() -> None:
    research_plan = plan(2)

    execution = asyncio.run(
        orchestrator(
            lambda assignment: WorkerProviderError()
            if assignment.worker_id == "worker-1"
            else result_for(assignment)
        ).execute(research_plan)
    )

    assert execution.workers[0].status is WorkerExecutionStatus.FAILED
    assert execution.workers[0].error.code == "provider_failure"
    assert execution.workers[1].result.worker_id == "worker-2"


def test_all_workers_failing_raises_job_error() -> None:
    with pytest.raises(AllWorkersFailedError) as exc_info:
        asyncio.run(
            orchestrator(lambda assignment: WorkerProviderError()).execute(plan(2))
        )

    assert [outcome.worker_id for outcome in exc_info.value.outcomes] == [
        "worker-1",
        "worker-2",
    ]
    assert all(outcome.error is not None for outcome in exc_info.value.outcomes)


def test_worker_timeout_is_captured_when_another_worker_succeeds() -> None:
    execution = asyncio.run(
        orchestrator(
            lambda assignment: WorkerTimeoutError()
            if assignment.worker_id == "worker-1"
            else result_for(assignment)
        ).execute(plan(2))
    )

    assert execution.workers[0].error.code == "timeout"
    assert execution.workers[1].status is WorkerExecutionStatus.SUCCEEDED


def test_malformed_worker_result_is_captured() -> None:
    execution = asyncio.run(
        orchestrator(
            lambda assignment: {"worker_id": assignment.worker_id}
            if assignment.worker_id == "worker-1"
            else result_for(assignment)
        ).execute(plan(2))
    )

    assert execution.workers[0].error.code == "invalid_result"


def test_successful_results_remain_grounded_and_validated() -> None:
    execution = asyncio.run(orchestrator(result_for).execute(plan(2)))

    validated = ResearchExecutionResult.model_validate(execution.model_dump())

    assert all(outcome.result is not None for outcome in validated.workers)


def test_more_than_five_workers_is_rejected_before_execution() -> None:
    data = plan(5).model_dump()
    data["worker_count"] = 6
    data["assignments"].append(
        {
            "worker_id": "worker-6",
            "focused_task": "Research area 6",
            "investigation_focus": "Investigate evidence area 6",
            "evidence_to_find": ["Evidence type 6"],
        }
    )

    with pytest.raises(ValidationError):
        ResearchPlan.model_validate(data)


def test_duplicate_worker_ids_are_rejected_before_execution() -> None:
    data = plan(2).model_dump()
    data["assignments"][1]["worker_id"] = "worker-1"

    with pytest.raises(ValidationError, match="worker IDs must be unique"):
        ResearchPlan.model_validate(data)
