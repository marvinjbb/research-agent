import json
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from research_agent.schemas import SearchSource, WorkerAnalysis, WorkerAssignment
from research_agent.workers.base import WorkerProviderError, WorkerTimeoutError

SYSTEM_PROMPT = """Analyze only the supplied web-search sources for one assignment.
Return exactly the WorkerAnalysis schema. Every factual claim must cite at least one
supplied source_id and copy a supporting excerpt verbatim from that source's snippet. Do not use
outside knowledge as evidence. Do not present unsupported inferences as established facts;
record gaps, conflicts, weak coverage, and limitations under uncertainties. Do not search,
call tools, execute other workers, or synthesize a final research report."""


class OpenAIWorkerResearchProvider:
    """OpenAI Structured Outputs adapter for source-grounded worker analysis."""

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

    async def analyze(
        self,
        assignment: WorkerAssignment,
        sources: list[SearchSource],
    ) -> WorkerAnalysis:
        source_payload = [source.model_dump(mode="json") for source in sources]
        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Assignment:\n{assignment.model_dump_json(indent=2)}\n\n"
                            f"Sources:\n{json.dumps(source_payload, indent=2)}"
                        ),
                    },
                ],
                text_format=WorkerAnalysis,
            )
            if response.output_parsed is None:
                raise WorkerProviderError("provider returned no structured worker analysis")
            return WorkerAnalysis.model_validate(response.output_parsed)
        except (APITimeoutError, TimeoutError) as exc:
            raise WorkerTimeoutError("worker analysis timed out") from exc
        except WorkerProviderError:
            raise
        except (APIError, ValidationError) as exc:
            raise WorkerProviderError("provider failed to create worker analysis") from exc
