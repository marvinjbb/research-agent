from typing import Protocol

from research_agent.schemas import ResearchPlan, ResearchRequest


class PlannerError(Exception):
    """Base error raised by a research planner implementation."""


class PlannerProviderError(PlannerError):
    """The configured provider could not produce a valid plan."""


class PlannerTimeoutError(PlannerError):
    """The configured provider exceeded the planning timeout."""


class ResearchPlanner(Protocol):
    """Provider-neutral contract for creating a validated research plan."""

    async def plan(self, request: ResearchRequest) -> ResearchPlan:
        """Create a plan without executing any worker assignments."""
        ...
