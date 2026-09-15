import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from research_agent.planning.base import PlannerProviderError, PlannerTimeoutError
from research_agent.planning.openai_planner import OpenAIResearchPlanner
from research_agent.schemas import ResearchDepth, ResearchPlan, ResearchRequest, WorkerAssignment


def valid_plan() -> ResearchPlan:
    return ResearchPlan(
        original_question="Question",
        objective="Objective",
        strategy="Strategy",
        worker_count=2,
        assignments=[
            WorkerAssignment(
                worker_id="worker-1",
                focused_task="Primary evidence",
                investigation_focus="Investigate supporting evidence",
                evidence_to_find=["Current primary sources"],
            ),
            WorkerAssignment(
                worker_id="worker-2",
                focused_task="Conflicting evidence",
                investigation_focus="Investigate counterarguments",
                evidence_to_find=["Credible contrary findings"],
            ),
        ],
    )


def planner_with(parse: AsyncMock) -> OpenAIResearchPlanner:
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    return OpenAIResearchPlanner(
        api_key="test-key",
        model="test-model",
        timeout_seconds=1,
        client=client,
    )


@pytest.mark.parametrize("depth", list(ResearchDepth))
def test_request_depth_is_passed_to_provider(depth: ResearchDepth) -> None:
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=valid_plan()))
    planner = planner_with(parse)

    asyncio.run(planner.plan(ResearchRequest(question="Question", depth=depth)))

    provider_input = parse.await_args.kwargs["input"]
    assert f"Research depth: {depth.value}" in provider_input[1]["content"]
    assert parse.await_args.kwargs["text_format"] is ResearchPlan


def test_provider_failure_is_normalized() -> None:
    provider_failure = APIConnectionError(request=httpx.Request("POST", "https://example.test"))
    planner = planner_with(AsyncMock(side_effect=provider_failure))

    with pytest.raises(PlannerProviderError):
        asyncio.run(planner.plan(ResearchRequest(question="Question")))


def test_provider_timeout_is_normalized() -> None:
    provider_timeout = APITimeoutError(request=httpx.Request("POST", "https://example.test"))
    planner = planner_with(AsyncMock(side_effect=provider_timeout))

    with pytest.raises(PlannerTimeoutError):
        asyncio.run(planner.plan(ResearchRequest(question="Question")))


def test_original_question_comes_from_validated_request() -> None:
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=valid_plan()))
    planner = planner_with(parse)

    result = asyncio.run(planner.plan(ResearchRequest(question="Canonical question")))

    assert result.original_question == "Canonical question"
