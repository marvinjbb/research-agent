from typing import Protocol

from pydantic import ValidationError

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
        try:
            plan = ResearchPlan.model_validate(await self._planner.plan(request))
            execution = ResearchExecutionResult.model_validate(
                await self._executor.execute(plan)
            )
            return FinalResearchReport.model_validate(
                await self._report_service.synthesize(execution)
            )
        except ValidationError as exc:
            raise WorkflowValidationError(
                "workflow component returned invalid structured output"
            ) from exc
