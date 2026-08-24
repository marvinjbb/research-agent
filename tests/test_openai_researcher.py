import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from research_agent.schemas import EvidenceCandidate, WorkerAnalysis, WorkerAssignment
from research_agent.workers.base import WorkerProviderError, WorkerTimeoutError
from research_agent.workers.openai_researcher import OpenAIWorkerResearchProvider


def assignment() -> WorkerAssignment:
    return WorkerAssignment(
        worker_id="worker-1",
        focused_task="Assess adoption",
        investigation_focus="Investigate current adoption",
        evidence_to_find=["Recent surveys"],
    )


def candidates() -> list[EvidenceCandidate]:
    return [
        EvidenceCandidate(
            evidence_id="evidence-1",
            source_id="source-1",
            source_title="Survey",
            source_url="https://example.com/survey",
            evidence="The survey reports increased adoption.",
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
                "evidence_ids": ["evidence-1"],
            }
        ],
        uncertainties=["Limited sample."],
    )
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))

    result = asyncio.run(provider_with(parse).analyze(assignment(), candidates()))

    assert result == parsed
    assert parse.await_args.kwargs["text_format"] is WorkerAnalysis
    content = parse.await_args.kwargs["input"][1]["content"]
    assert "evidence-1" in content
    assert "evidence_ids" in parse.await_args.kwargs["input"][0]["content"]


def test_worker_provider_failure_is_normalized() -> None:
    error = APIConnectionError(request=httpx.Request("POST", "https://example.test"))

    with pytest.raises(WorkerProviderError):
        asyncio.run(
            provider_with(AsyncMock(side_effect=error)).analyze(
                assignment(), candidates()
            )
        )


def test_worker_provider_timeout_is_normalized() -> None:
    error = APITimeoutError(request=httpx.Request("POST", "https://example.test"))

    with pytest.raises(WorkerTimeoutError):
        asyncio.run(
            provider_with(AsyncMock(side_effect=error)).analyze(
                assignment(), candidates()
            )
        )
