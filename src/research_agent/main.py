from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import ValidationError

from research_agent.config import PlannerSettings, TavilySettings
from research_agent.planning.base import (
    PlannerProviderError,
    PlannerTimeoutError,
    ResearchPlanner,
)
from research_agent.planning.openai_planner import OpenAIResearchPlanner
from research_agent.schemas import (
    HealthResponse,
    ResearchPlan,
    ResearchRequest,
    WorkerAssignment,
    WorkerResult,
)
from research_agent.search.base import SearchProvider, SearchProviderError, SearchTimeoutError
from research_agent.search.tavily import TavilySearchProvider
from research_agent.workers.base import (
    EmptySearchResultsError,
    WorkerEvidenceError,
    WorkerProviderError,
    WorkerResearchProvider,
    WorkerTimeoutError,
)
from research_agent.workers.openai_researcher import OpenAIWorkerResearchProvider
from research_agent.workers.single_worker import SingleResearchWorker

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


def get_search_provider() -> SearchProvider:
    """Build the configured bounded Tavily search adapter."""
    try:
        settings = TavilySettings()
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="web search provider is not configured",
        ) from exc
    return TavilySearchProvider(
        api_key=settings.tavily_api_key.get_secret_value(),
        timeout_seconds=settings.tavily_timeout_seconds,
    )


def get_worker_research_provider() -> WorkerResearchProvider:
    """Build the configured OpenAI worker-analysis adapter."""
    try:
        settings = PlannerSettings()
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="worker analysis provider is not configured",
        ) from exc
    return OpenAIWorkerResearchProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def get_worker(
    search_provider: Annotated[SearchProvider, Depends(get_search_provider)],
    research_provider: Annotated[
        WorkerResearchProvider,
        Depends(get_worker_research_provider),
    ],
) -> SingleResearchWorker:
    """Compose one worker from application-owned provider boundaries."""
    return SingleResearchWorker(
        search_provider=search_provider,
        research_provider=research_provider,
    )


@app.post("/research/worker", response_model=WorkerResult)
async def run_single_worker(
    assignment: WorkerAssignment,
    worker: Annotated[SingleResearchWorker, Depends(get_worker)],
) -> WorkerResult:
    """Research one existing assignment without orchestration or synthesis."""
    try:
        return await worker.research(assignment)
    except (SearchTimeoutError, WorkerTimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="single-worker research timed out",
        ) from exc
    except EmptySearchResultsError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="web search returned no usable sources",
        ) from exc
    except WorkerEvidenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="worker result contains unsupported evidence",
        ) from exc
    except (SearchProviderError, WorkerProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="single-worker provider failed",
        ) from exc
