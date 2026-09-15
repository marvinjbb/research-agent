import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from research_agent.schemas import EvidenceBundle, SynthesisDraft
from research_agent.synthesis.base import (
    SynthesisProviderError,
    SynthesisTimeoutError,
)
from research_agent.synthesis.openai_synthesizer import OpenAIResearchSynthesizer


def evidence_bundle() -> EvidenceBundle:
    return EvidenceBundle.model_validate(
        {
            "original_question": "Question?",
            "objective": "Assess evidence.",
            "strategy": "Compare sources.",
            "sources": [
                {
                    "source_id": "source-1",
                    "title": "Report",
                    "url": "https://example.com/report",
                    "snippets": ["The report supports the claim."],
                    "validated_excerpts": ["The report supports the claim."],
                    "provenance": [{"worker_id": "worker-1", "worker_source_id": "source-1"}],
                }
            ],
            "claims": [
                {
                    "claim_id": "claim-1",
                    "statement": "The claim is supported.",
                    "evidence": [
                        {
                            "source_id": "source-1",
                            "evidence": "The report supports the claim.",
                        }
                    ],
                    "worker_ids": ["worker-1"],
                }
            ],
            "uncertainties": [
                {
                    "uncertainty_id": "uncertainty-1",
                    "worker_id": "worker-1",
                    "statement": "Evidence is limited.",
                }
            ],
        }
    )


def draft() -> SynthesisDraft:
    bundle = evidence_bundle()
    selection = {
        "claim_id": "claim-1",
        "evidence_ids": [bundle.claims[0].evidence[0].evidence_id],
    }
    return SynthesisDraft.model_validate(
        {
            "executive_summary": [selection],
            "key_findings": [selection],
            "important_claims": [selection],
            "uncertainties": [{"uncertainty_id": "uncertainty-1"}],
        }
    )


def provider_with(parse: AsyncMock) -> OpenAIResearchSynthesizer:
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    return OpenAIResearchSynthesizer(
        api_key="test-key",
        model="test-model",
        timeout_seconds=1,
        client=client,
    )


def test_synthesizer_uses_structured_output_and_only_bundle_input() -> None:
    parsed = draft()
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))

    result = asyncio.run(provider_with(parse).synthesize(evidence_bundle()))

    assert result == parsed
    assert parse.await_args.kwargs["text_format"] is SynthesisDraft
    assert "validated_excerpts" in parse.await_args.kwargs["input"][1]["content"]


def test_synthesis_adapter_normalizes_provider_failure() -> None:
    error = APIConnectionError(request=httpx.Request("POST", "https://example.test"))

    with pytest.raises(SynthesisProviderError):
        asyncio.run(provider_with(AsyncMock(side_effect=error)).synthesize(evidence_bundle()))


def test_synthesis_adapter_normalizes_timeout() -> None:
    error = APITimeoutError(request=httpx.Request("POST", "https://example.test"))

    with pytest.raises(SynthesisTimeoutError):
        asyncio.run(provider_with(AsyncMock(side_effect=error)).synthesize(evidence_bundle()))


def test_synthesis_adapter_rejects_empty_structured_output() -> None:
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=None))

    with pytest.raises(SynthesisProviderError):
        asyncio.run(provider_with(parse).synthesize(evidence_bundle()))
