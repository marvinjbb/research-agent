from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from research_agent.planning.base import PlannerProviderError, PlannerTimeoutError
from research_agent.schemas import ResearchPlan, ResearchRequest

SYSTEM_PROMPT = """You create bounded research plans, not research results.
Return exactly the supplied ResearchPlan structure. Create 2 to 5 focused,
non-duplicative worker assignments. Each worker must have one clear responsibility.
Use the requested depth as planning context: quick plans should generally use fewer
workers and narrower assignments than deep plans. When relevant, cover counterarguments,
risks, conflicting evidence, or alternative perspectives. Do not execute research,
search the web, synthesize a report, or invent fields outside the schema."""


class OpenAIResearchPlanner:
    """OpenAI Structured Outputs adapter for the application planner interface."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._client = client or AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

    async def plan(self, request: ResearchRequest) -> ResearchPlan:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Research depth: {request.depth.value}\n"
                            f"Research question: {request.question}"
                        ),
                    },
                ],
                text_format=ResearchPlan,
            )
            if response.output_parsed is None:
                raise PlannerProviderError("provider returned no structured research plan")
            plan = ResearchPlan.model_validate(response.output_parsed)
            return plan.model_copy(update={"original_question": request.question})
        except (APITimeoutError, TimeoutError) as exc:
            raise PlannerTimeoutError("research planning timed out") from exc
        except PlannerProviderError:
            raise
        except (APIError, ValidationError) as exc:
            raise PlannerProviderError("provider failed to create a valid research plan") from exc
