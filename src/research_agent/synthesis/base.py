from typing import Protocol

from research_agent.schemas import EvidenceBundle, SynthesisDraft


class SynthesisError(Exception):
    """Base error raised while producing a final report."""


class SynthesisProviderError(SynthesisError):
    """The synthesis provider failed or returned malformed output."""


class SynthesisTimeoutError(SynthesisError):
    """The synthesis provider exceeded its configured timeout."""


class SynthesisEvidenceError(SynthesisError):
    """The synthesis output was not grounded in aggregated worker evidence."""


class NoSuccessfulWorkersError(SynthesisError):
    """The execution contains no successful worker evidence."""


class ResearchSynthesizer(Protocol):
    """Provider-neutral interface for structured report synthesis."""

    async def synthesize(self, evidence: EvidenceBundle) -> SynthesisDraft:
        """Create a structured draft using only the supplied evidence."""
        ...
