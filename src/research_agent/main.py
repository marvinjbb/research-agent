from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from research_agent.config import PlannerSettings, SynthesisSettings, TavilySettings
from research_agent.observability import (
    configure_logging,
    create_request_id,
    log_event,
    reset_request_id,
    set_request_id,
)
from research_agent.orchestration.parallel import (
    AllWorkersFailedError,
    ParallelResearchOrchestrator,
)
from research_agent.planning.base import (
    PlannerProviderError,
    PlannerTimeoutError,
    ResearchPlanner,
)
from research_agent.planning.openai_planner import OpenAIResearchPlanner
from research_agent.public_api import enforce_public_research_limit, public_api_settings
from research_agent.schemas import (
    FinalResearchReport,
    HealthResponse,
    ResearchExecutionResult,
    ResearchPlan,
    ResearchRequest,
    WorkerAssignment,
    WorkerResult,
)
from research_agent.search.base import SearchProvider, SearchProviderError, SearchTimeoutError
from research_agent.search.tavily import TavilySearchProvider
from research_agent.synthesis.aggregate import EvidenceAggregator
from research_agent.synthesis.base import (
    NoSuccessfulWorkersError,
    SynthesisEvidenceError,
    SynthesisProviderError,
    SynthesisTimeoutError,
)
from research_agent.synthesis.openai_synthesizer import OpenAIResearchSynthesizer
from research_agent.synthesis.service import ResearchSynthesisService
from research_agent.workers.base import (
    EmptySearchResultsError,
    WorkerEvidenceError,
    WorkerProviderError,
    WorkerResearchProvider,
    WorkerTimeoutError,
)
from research_agent.workers.openai_researcher import OpenAIWorkerResearchProvider
from research_agent.workers.single_worker import SingleResearchWorker
from research_agent.workflow.service import ResearchWorkflow, WorkflowValidationError

configure_logging()

app = FastAPI(
    title="Research Agent",
    description="Bounded multi-agent web research with evidence-grounded cited reports.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(public_api_settings.cors_allowed_origin).rstrip("/")],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def observe_request(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Add a safe correlation ID and emit bounded request telemetry."""
    request_id = create_request_id()
    token = set_request_id(request_id)
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log_event(
            "http_request_completed",
            path=request.url.path,
            status_code=500,
            duration_ms=round((perf_counter() - started) * 1_000, 2),
            error_category="unhandled_error",
        )
        raise
    else:
        response.headers["X-Request-ID"] = request_id
        log_event(
            "http_request_completed",
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started) * 1_000, 2),
        )
        return response
    finally:
        reset_request_id(token)


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


@app.post(
    "/research/plan",
    response_model=ResearchPlan,
    dependencies=[Depends(enforce_public_research_limit)],
)
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


def get_research_orchestrator(
    search_provider: Annotated[SearchProvider, Depends(get_search_provider)],
    research_provider: Annotated[
        WorkerResearchProvider,
        Depends(get_worker_research_provider),
    ],
) -> ParallelResearchOrchestrator:
    """Compose bounded orchestration separately from the HTTP route."""
    return ParallelResearchOrchestrator(
        worker_factory=lambda: SingleResearchWorker(
            search_provider=search_provider,
            research_provider=research_provider,
        )
    )


@app.post(
    "/research/worker",
    response_model=WorkerResult,
    dependencies=[Depends(enforce_public_research_limit)],
)
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


@app.post(
    "/research/execute",
    response_model=ResearchExecutionResult,
    dependencies=[Depends(enforce_public_research_limit)],
)
async def execute_research_plan(
    plan: ResearchPlan,
    orchestrator: Annotated[
        ParallelResearchOrchestrator,
        Depends(get_research_orchestrator),
    ],
) -> ResearchExecutionResult:
    """Execute a validated plan without synthesis or replacement workers."""
    try:
        return await orchestrator.execute(plan)
    except AllWorkersFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail={
                "message": "all research workers failed",
                "workers": [outcome.model_dump(mode="json") for outcome in exc.outcomes],
            },
        ) from exc


def get_synthesis_service() -> ResearchSynthesisService:
    """Compose deterministic aggregation with the configured synthesis adapter."""
    try:
        settings = SynthesisSettings()
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="research synthesis provider is not configured",
        ) from exc
    return ResearchSynthesisService(
        aggregator=EvidenceAggregator(),
        synthesizer=OpenAIResearchSynthesizer(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_synthesis_model,
            timeout_seconds=settings.openai_synthesis_timeout_seconds,
        ),
    )


@app.post(
    "/research/synthesize",
    response_model=FinalResearchReport,
    dependencies=[Depends(enforce_public_research_limit)],
)
async def synthesize_research_report(
    execution: ResearchExecutionResult,
    service: Annotated[
        ResearchSynthesisService,
        Depends(get_synthesis_service),
    ],
) -> FinalResearchReport:
    """Produce a final report from validated worker evidence only."""
    try:
        return await service.synthesize(execution)
    except SynthesisTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="research synthesis timed out",
        ) from exc
    except SynthesisEvidenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="research synthesis contains unsupported evidence",
        ) from exc
    except NoSuccessfulWorkersError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="research execution has no successful workers",
        ) from exc
    except SynthesisProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="research synthesis provider failed",
        ) from exc


def get_research_workflow(
    planner: Annotated[ResearchPlanner, Depends(get_planner)],
    orchestrator: Annotated[
        ParallelResearchOrchestrator,
        Depends(get_research_orchestrator),
    ],
    synthesis_service: Annotated[
        ResearchSynthesisService,
        Depends(get_synthesis_service),
    ],
) -> ResearchWorkflow:
    """Compose the proven phases into one request-scoped workflow."""
    return ResearchWorkflow(
        planner=planner,
        executor=orchestrator,
        report_service=synthesis_service,
    )


@app.post(
    "/research",
    response_model=FinalResearchReport,
    dependencies=[Depends(enforce_public_research_limit)],
)
async def run_research_workflow(
    request: ResearchRequest,
    workflow: Annotated[ResearchWorkflow, Depends(get_research_workflow)],
) -> FinalResearchReport:
    """Run planning, bounded workers, and grounded synthesis once."""
    try:
        return await workflow.research(request)
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
    except AllWorkersFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail={
                "message": "all research workers failed",
                "workers": [outcome.model_dump(mode="json") for outcome in exc.outcomes],
            },
        ) from exc
    except SynthesisTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="research synthesis timed out",
        ) from exc
    except SynthesisEvidenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="research synthesis contains unsupported evidence",
        ) from exc
    except NoSuccessfulWorkersError as exc:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail="research execution has no successful workers",
        ) from exc
    except SynthesisProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="research synthesis provider failed",
        ) from exc
    except WorkflowValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="research workflow returned invalid structured output",
        ) from exc
