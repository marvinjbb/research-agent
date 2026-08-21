import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from research_agent.schemas import SearchSource, WorkerAnalysis, WorkerAssignment
from research_agent.workers.base import WorkerProviderError, WorkerTimeoutError
from research_agent.workers.openai_researcher import OpenAIWorkerResearchProvider


def assignment() -> WorkerAssignment:
    return WorkerAssignment(
        worker_id="worker-1",
        focused_task="Assess adoption",
        investigation_focus="Investigate current adoption",
        evidence_to_find=["Recent surveys"],
    )


def sources() -> list[SearchSource]:
    return [
        SearchSource(
            source_id="source-1",
            title="Survey",
            url="https://example.com/survey",
            snippet="The survey reports increased adoption.",
        )
    ]


def provider_with(parse: AsyncMock) -> OpenAIWorkerResearchProvider:
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    return OpenAIWorkerResearchProvider(
        api_key="test-key",
        model="test-model",
        timeout_seconds=1,
        client=client,
    )


def test_provider_uses_structured_output_and_supplied_sources() -> None:
    parsed = WorkerAnalysis(
        claims=[
            {
                "claim": "Adoption increased.",
                "evidence": [
                    {"source_id": "source-1", "evidence": "Survey reports growth."}
                ],
            }
        ],
        uncertainties=["Limited sample."],
    )
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))

    result = asyncio.run(provider_with(parse).analyze(assignment(), sources()))

    assert result == parsed
    assert parse.await_args.kwargs["text_format"] is WorkerAnalysis
    assert "source-1" in parse.await_args.kwargs["input"][1]["content"]


def test_worker_provider_failure_is_normalized() -> None:
    error = APIConnectionError(request=httpx.Request("POST", "https://example.test"))

    with pytest.raises(WorkerProviderError):
        asyncio.run(provider_with(AsyncMock(side_effect=error)).analyze(assignment(), sources()))


def test_worker_provider_timeout_is_normalized() -> None:
    error = APITimeoutError(request=httpx.Request("POST", "https://example.test"))

    with pytest.raises(WorkerTimeoutError):
        asyncio.run(provider_with(AsyncMock(side_effect=error)).analyze(assignment(), sources()))
