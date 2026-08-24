from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from research_agent.schemas import EvidenceBundle, SynthesisDraft
from research_agent.synthesis.base import (
    SynthesisProviderError,
    SynthesisTimeoutError,
)

SYSTEM_PROMPT = """Create a final research-report draft using only the supplied EvidenceBundle.
Return exactly the SynthesisDraft schema. Every factual statement and recommendation must
cite one or more supplied source_id values and copy evidence exactly from that source's
validated_excerpts. Never invent evidence, citations, source IDs, or external knowledge.
Every factual report statement must copy a supplied claim statement exactly, include its
claim_id, and use only evidence attached to that claim. Keep findings, conflicts,
uncertainties, and recommendations in their separate schema sections. Preserve materially
competing claims as conflict positions instead of silently choosing one. Uncertainties
must copy supplied uncertainty text exactly and attribute its worker_id. Do not search,
call tools, retry, or execute workers."""


class OpenAIResearchSynthesizer:
    """OpenAI Structured Outputs adapter for grounded report synthesis."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
        )
        self._model = model

    async def synthesize(self, evidence: EvidenceBundle) -> SynthesisDraft:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": evidence.model_dump_json(indent=2)},
                ],
                text_format=SynthesisDraft,
            )
            if response.output_parsed is None:
                raise SynthesisProviderError(
                    "provider returned no structured synthesis"
                )
            return SynthesisDraft.model_validate(response.output_parsed)
        except (APITimeoutError, TimeoutError) as exc:
            raise SynthesisTimeoutError("research synthesis timed out") from exc
        except SynthesisProviderError:
            raise
        except (APIError, ValidationError) as exc:
            raise SynthesisProviderError("research synthesis provider failed") from exc
