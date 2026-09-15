from time import perf_counter
from typing import Protocol

from pydantic import ValidationError

from research_agent.observability import log_event
from research_agent.planning.base import ResearchPlanner
from research_agent.schemas import (
    FinalResearchReport,
    ResearchExecutionResult,
    ResearchPlan,
    ResearchRequest,
)


class ResearchPlanExecutor(Protocol):
    """Application boundary for executing one validated plan."""

    async def execute(self, plan: ResearchPlan) -> ResearchExecutionResult:
        """Execute the plan's bounded worker assignments."""
        ...


class ResearchReportService(Protocol):
    """Application boundary for synthesizing one validated execution."""

    async def synthesize(
        self,
        execution: ResearchExecutionResult,
    ) -> FinalResearchReport:
        """Return a grounded final report."""
        ...


class WorkflowValidationError(Exception):
    """A workflow component returned invalid application-owned structure."""


class ResearchWorkflow:
    """Compose planning, execution, and synthesis for one in-memory request."""

    def __init__(
        self,
        *,
        planner: ResearchPlanner,
        executor: ResearchPlanExecutor,
        report_service: ResearchReportService,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._report_service = report_service

    async def research(self, request: ResearchRequest) -> FinalResearchReport:
        started = perf_counter()
        log_event("research_workflow_started", research_mode=request.depth.value)
        try:
            plan = ResearchPlan.model_validate(await self._planner.plan(request))
            log_event(
                "research_plan_completed",
                research_mode=request.depth.value,
                worker_count=plan.worker_count,
                outcome="succeeded",
            )
            execution = ResearchExecutionResult.model_validate(await self._executor.execute(plan))
            report = FinalResearchReport.model_validate(
                await self._report_service.synthesize(execution)
            )
        except ValidationError as exc:
            log_event(
                "research_workflow_failed",
                research_mode=request.depth.value,
                duration_ms=round((perf_counter() - started) * 1_000, 2),
                error_category="invalid_structured_output",
            )
            raise WorkflowValidationError(
                "workflow component returned invalid structured output"
            ) from exc
        except Exception as exc:
            known_categories = {
                "AllWorkersFailedError": "all_workers_failed",
                "NoSuccessfulWorkersError": "no_successful_workers",
                "PlannerProviderError": "planner_provider_failure",
                "PlannerTimeoutError": "planner_timeout",
                "SynthesisEvidenceError": "invalid_synthesis_evidence",
                "SynthesisProviderError": "synthesis_provider_failure",
                "SynthesisTimeoutError": "synthesis_timeout",
            }
            log_event(
                "research_workflow_failed",
                research_mode=request.depth.value,
                duration_ms=round((perf_counter() - started) * 1_000, 2),
                error_category=known_categories.get(
                    type(exc).__name__, "unexpected_application_error"
                ),
            )
            raise

        successful_workers = sum(worker.result is not None for worker in execution.workers)
        log_event(
            "research_workflow_completed",
            research_mode=request.depth.value,
            duration_ms=round((perf_counter() - started) * 1_000, 2),
            worker_count=execution.worker_count,
            successful_worker_count=successful_workers,
            failed_worker_count=execution.worker_count - successful_workers,
            source_count=len(report.sources),
            outcome="succeeded",
        )
        return report
