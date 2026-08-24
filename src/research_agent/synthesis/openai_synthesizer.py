from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from research_agent.schemas import EvidenceBundle, SynthesisDraft
from research_agent.synthesis.base import (
    SynthesisProviderError,
    SynthesisTimeoutError,
)

SYSTEM_PROMPT = """Create final-report selections using only the supplied EvidenceBundle.
Return exactly the SynthesisDraft schema. For executive summary, key findings, and important
claims, select claim_id and evidence_ids attached to that claim. For conflict positions,
select competing claim IDs and their attached evidence IDs. Select uncertainty_id values;
never reproduce uncertainty text. Recommendations and rationales may be authored as
inference, but must select claim_ids and evidence_ids attached to those claims. Never copy,
edit, paraphrase, or invent factual claim text or evidence text. Never invent IDs or use
external knowledge. Do not search, call tools, retry, or execute workers."""


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
