import asyncio
from typing import Any

import pytest

from research_agent.orchestration.parallel import AllWorkersFailedError
from research_agent.planning.base import PlannerProviderError, PlannerTimeoutError
from research_agent.schemas import (
    FinalResearchReport,
    ResearchExecutionResult,
    ResearchPlan,
    ResearchRequest,
    WorkerAssignment,
    WorkerExecutionOutcome,
)
from research_agent.synthesis.base import (
    SynthesisProviderError,
    SynthesisTimeoutError,
)
from research_agent.workflow.service import ResearchWorkflow, WorkflowValidationError


def assignment(index: int) -> WorkerAssignment:
    return WorkerAssignment(
        worker_id=f"worker-{index}",
        focused_task=f"Research area {index}",
        investigation_focus=f"Investigate area {index}",
        evidence_to_find=[f"Evidence type {index}"],
    )


def plan_for(request: ResearchRequest, worker_count: int) -> ResearchPlan:
    return ResearchPlan(
        original_question=request.question,
        objective=f"Assess the question at {request.depth.value} depth.",
        strategy=f"Use {worker_count} focused assignments.",
        worker_count=worker_count,
        assignments=[assignment(index) for index in range(1, worker_count + 1)],
    )


def successful_outcome(worker_assignment: WorkerAssignment) -> dict[str, Any]:
    evidence = f"Validated evidence from {worker_assignment.worker_id}."
    return {
        "worker_id": worker_assignment.worker_id,
        "assignment": worker_assignment,
        "status": "succeeded",
        "result": {
            "worker_id": worker_assignment.worker_id,
            "assignment": worker_assignment,
            "claims": [
                {
                    "claim": f"Grounded claim from {worker_assignment.worker_id}.",
                    "evidence": [{"source_id": "source-1", "evidence": evidence}],
                }
            ],
            "sources": [
                {
                    "source_id": "source-1",
                    "title": f"Source for {worker_assignment.worker_id}",
                    "url": f"https://example.com/{worker_assignment.worker_id}",
                    "snippet": evidence,
                }
            ],
            "uncertainties": [f"Uncertainty from {worker_assignment.worker_id}."],
        },
    }


def failed_outcome(worker_assignment: WorkerAssignment) -> dict[str, Any]:
    return {
        "worker_id": worker_assignment.worker_id,
        "assignment": worker_assignment,
        "status": "failed",
        "error": {"code": "timeout", "message": "worker execution timed out"},
    }


def execution_for(
    plan: ResearchPlan,
    *,
    fail_first: bool = False,
) -> ResearchExecutionResult:
    outcomes = [successful_outcome(item) for item in plan.assignments]
    if fail_first:
        outcomes[0] = failed_outcome(plan.assignments[0])
    return ResearchExecutionResult(
        original_question=plan.original_question,
        objective=plan.objective,
        strategy=plan.strategy,
        worker_count=plan.worker_count,
        workers=outcomes,
    )


def report_for(execution: ResearchExecutionResult) -> FinalResearchReport:
    successful = next(outcome for outcome in execution.workers if outcome.result is not None)
    result = successful.result
    assert result is not None
    claim = result.claims[0]
    evidence = claim.evidence[0]
    source = result.sources[0]
    statement = {
        "statement": claim.claim,
        "claim_ids": ["claim-1"],
        "citations": [evidence.model_dump()],
    }
    failed = [
        {
            "worker_id": outcome.worker_id,
            "assignment": outcome.assignment,
            "code": outcome.error.code,
            "message": outcome.error.message,
        }
        for outcome in execution.workers
        if outcome.error is not None
    ]
    return FinalResearchReport.model_validate(
        {
            "original_question": execution.original_question,
            "objective": execution.objective,
            "strategy": execution.strategy,
            "executive_summary": [statement],
            "key_findings": [statement],
            "important_claims": [statement],
            "uncertainties": [
                {
                    "statement": result.uncertainties[0],
                    "worker_ids": [result.worker_id],
                }
            ],
            "evidence_claims": [
                {
                    "claim_id": "claim-1",
                    "statement": claim.claim,
                    "evidence": [evidence.model_dump()],
                    "worker_ids": [result.worker_id],
                }
            ],
            "sources": [
                {
                    "source_id": evidence.source_id,
                    "title": source.title,
                    "url": source.url,
                    "snippets": [source.snippet],
                    "validated_excerpts": [evidence.evidence],
                    "provenance": [
                        {
                            "worker_id": result.worker_id,
                            "worker_source_id": source.source_id,
                        }
                    ],
                }
            ],
            "failed_workers": failed,
        }
    )


class FakePlanner:
    def __init__(
        self,
        *,
        worker_count: int = 2,
        error: Exception | None = None,
        result: Any = None,
    ) -> None:
        self.worker_count = worker_count
        self.error = error
        self.result = result
        self.received: list[ResearchRequest] = []

    async def plan(self, request: ResearchRequest) -> Any:
        self.received.append(request)
        if self.error:
            raise self.error
        return self.result if self.result is not None else plan_for(request, self.worker_count)


class FakeExecutor:
    def __init__(
        self,
        *,
        fail_first: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.fail_first = fail_first
        self.error = error
        self.received: list[ResearchPlan] = []

    async def execute(self, plan: ResearchPlan) -> ResearchExecutionResult:
        self.received.append(plan)
        if self.error:
            raise self.error
        return execution_for(plan, fail_first=self.fail_first)


class FakeReportService:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        result: Any = None,
    ) -> None:
        self.error = error
        self.result = result
        self.received: list[ResearchExecutionResult] = []

    async def synthesize(self, execution: ResearchExecutionResult) -> Any:
        self.received.append(execution)
        if self.error:
            raise self.error
        return self.result if self.result is not None else report_for(execution)


def workflow(
    planner: FakePlanner | None = None,
    executor: FakeExecutor | None = None,
    report_service: FakeReportService | None = None,
) -> tuple[ResearchWorkflow, FakePlanner, FakeExecutor, FakeReportService]:
    planner = planner or FakePlanner()
    executor = executor or FakeExecutor()
    report_service = report_service or FakeReportService()
    return (
        ResearchWorkflow(
            planner=planner,
            executor=executor,
            report_service=report_service,
        ),
        planner,
        executor,
        report_service,
    )


@pytest.mark.parametrize("depth", ["quick", "deep"])
def test_successful_workflow_preserves_request_depth(depth: str) -> None:
    service, planner, _, _ = workflow()
    request = ResearchRequest(question="Research question?", depth=depth)

    report = asyncio.run(service.research(request))

    assert report.original_question == request.question
    assert planner.received[0].depth.value == depth


@pytest.mark.parametrize("worker_count", [2, 5])
def test_planner_worker_bounds_propagate_to_execution(worker_count: int) -> None:
    service, _, executor, _ = workflow(FakePlanner(worker_count=worker_count))

    asyncio.run(service.research(ResearchRequest(question="Question?")))

    assert executor.received[0].worker_count == worker_count
    assert len(executor.received[0].assignments) == worker_count


def test_partial_worker_failure_still_reaches_synthesis() -> None:
    service, _, _, report_service = workflow(executor=FakeExecutor(fail_first=True))

    report = asyncio.run(service.research(ResearchRequest(question="Question?")))

    assert report.failed_workers[0].worker_id == "worker-1"
    assert report_service.received[0].workers[0].status.value == "failed"


def test_all_worker_failure_is_preserved() -> None:
    research_plan = plan_for(ResearchRequest(question="Question?"), 2)
    outcomes = [
        WorkerExecutionOutcome.model_validate(failed_outcome(item))
        for item in research_plan.assignments
    ]
    service, _, _, _ = workflow(executor=FakeExecutor(error=AllWorkersFailedError(outcomes)))

    with pytest.raises(AllWorkersFailedError):
        asyncio.run(service.research(ResearchRequest(question="Question?")))


@pytest.mark.parametrize(
    "error",
    [PlannerProviderError(), PlannerTimeoutError()],
)
def test_planning_failures_are_preserved(error: Exception) -> None:
    service, _, _, _ = workflow(planner=FakePlanner(error=error))

    with pytest.raises(type(error)):
        asyncio.run(service.research(ResearchRequest(question="Question?")))


@pytest.mark.parametrize(
    "error",
    [SynthesisProviderError(), SynthesisTimeoutError()],
)
def test_synthesis_failures_are_preserved(error: Exception) -> None:
    service, _, _, _ = workflow(report_service=FakeReportService(error=error))

    with pytest.raises(type(error)):
        asyncio.run(service.research(ResearchRequest(question="Question?")))


def test_invalid_final_output_is_rejected() -> None:
    service, _, _, _ = workflow(report_service=FakeReportService(result={"bad": "data"}))

    with pytest.raises(WorkflowValidationError):
        asyncio.run(service.research(ResearchRequest(question="Question?")))


def test_planner_to_executor_to_synthesis_data_propagation() -> None:
    service, planner, executor, report_service = workflow()
    request = ResearchRequest(question="Propagation question?", depth="deep")

    report = asyncio.run(service.research(request))

    assert executor.received[0].original_question == planner.received[0].question
    assert report_service.received[0].original_question == request.question
    assert report.original_question == request.question
