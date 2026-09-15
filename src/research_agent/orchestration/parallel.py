import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Protocol

from pydantic import ValidationError

from research_agent.observability import log_event
from research_agent.schemas import (
    ResearchExecutionResult,
    ResearchPlan,
    WorkerAssignment,
    WorkerExecutionOutcome,
    WorkerExecutionStatus,
    WorkerFailure,
    WorkerResult,
)
from research_agent.search.base import SearchProviderError, SearchTimeoutError
from research_agent.workers.base import (
    EmptySearchResultsError,
    WorkerEvidenceError,
    WorkerProviderError,
    WorkerTimeoutError,
)


class ResearchWorker(Protocol):
    """Application boundary for executing one existing assignment."""

    async def research(self, assignment: WorkerAssignment) -> WorkerResult:
        """Return one grounded worker result."""
        ...


WorkerFactory = Callable[[], ResearchWorker]


class AllWorkersFailedError(Exception):
    """Every bounded worker execution failed."""

    def __init__(self, outcomes: list[WorkerExecutionOutcome]) -> None:
        super().__init__("all research workers failed")
        self.outcomes = outcomes


class ParallelResearchOrchestrator:
    """Execute every validated plan assignment once as an in-process task."""

    def __init__(self, *, worker_factory: WorkerFactory) -> None:
        self._worker_factory = worker_factory

    async def execute(self, plan: ResearchPlan) -> ResearchExecutionResult:
        outcomes = await asyncio.gather(
            *(self._execute_assignment(assignment) for assignment in plan.assignments)
        )
        if not any(outcome.status is WorkerExecutionStatus.SUCCEEDED for outcome in outcomes):
            raise AllWorkersFailedError(outcomes)

        return ResearchExecutionResult(
            original_question=plan.original_question,
            objective=plan.objective,
            strategy=plan.strategy,
            worker_count=plan.worker_count,
            workers=outcomes,
        )

    async def _execute_assignment(
        self,
        assignment: WorkerAssignment,
    ) -> WorkerExecutionOutcome:
        worker = self._worker_factory()
        started = perf_counter()
        try:
            result = WorkerResult.model_validate(await worker.research(assignment))
            log_event(
                "research_worker_completed",
                worker_id=assignment.worker_id,
                outcome="succeeded",
                duration_ms=round((perf_counter() - started) * 1_000, 2),
                source_count=len(result.sources),
            )
            return WorkerExecutionOutcome(
                worker_id=assignment.worker_id,
                assignment=assignment,
                status=WorkerExecutionStatus.SUCCEEDED,
                result=result,
            )
        except (SearchTimeoutError, WorkerTimeoutError, TimeoutError):
            error = WorkerFailure(code="timeout", message="worker execution timed out")
        except EmptySearchResultsError:
            error = WorkerFailure(
                code="no_sources",
                message="worker found no usable sources",
            )
        except WorkerEvidenceError:
            error = WorkerFailure(
                code="invalid_evidence",
                message="worker returned unsupported evidence",
            )
        except ValidationError:
            error = WorkerFailure(
                code="invalid_result",
                message="worker returned a malformed result",
            )
        except (SearchProviderError, WorkerProviderError):
            error = WorkerFailure(
                code="provider_failure",
                message="worker provider failed",
            )

        log_event(
            "research_worker_completed",
            worker_id=assignment.worker_id,
            outcome="failed",
            duration_ms=round((perf_counter() - started) * 1_000, 2),
            error_category=error.code,
        )
        return WorkerExecutionOutcome(
            worker_id=assignment.worker_id,
            assignment=assignment,
            status=WorkerExecutionStatus.FAILED,
            error=error,
        )
