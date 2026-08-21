from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import ValidationError

from research_agent.config import PlannerSettings
from research_agent.planning.base import (
    PlannerProviderError,
    PlannerTimeoutError,
    ResearchPlanner,
)
from research_agent.planning.openai_planner import OpenAIResearchPlanner
from research_agent.schemas import HealthResponse, ResearchPlan, ResearchRequest

app = FastAPI(
    title="Research Agent",
    description="API foundation for a bounded multi-agent research system.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report whether the API process is available."""
    return HealthResponse(status="ok")


def get_planner() -> ResearchPlanner:
    """Build the configured provider adapter at the application boundary."""
    try:
        settings = PlannerSettings()
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="research planner is not configured",
        ) from exc

    return OpenAIResearchPlanner(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )


@app.post("/research/plan", response_model=ResearchPlan)
async def create_research_plan(
    request: ResearchRequest,
    planner: Annotated[ResearchPlanner, Depends(get_planner)],
) -> ResearchPlan:
    """Create and validate a plan without executing its assignments."""
    try:
        return await planner.plan(request)
    except PlannerTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="research planning timed out",
        ) from exc
    except PlannerProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="research planner provider failed",
        ) from exc
