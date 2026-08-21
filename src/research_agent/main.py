from fastapi import FastAPI

from research_agent.schemas import HealthResponse

app = FastAPI(
    title="Research Agent",
    description="API foundation for a bounded multi-agent research system.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report whether the API process is available."""
    return HealthResponse(status="ok")

