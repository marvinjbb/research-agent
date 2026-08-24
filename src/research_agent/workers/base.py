from typing import Protocol

from research_agent.schemas import EvidenceCandidate, WorkerAnalysis, WorkerAssignment


class WorkerError(Exception):
    """Base error raised while researching one assignment."""


class EmptySearchResultsError(WorkerError):
    """No usable sources were returned for the assignment."""


class WorkerProviderError(WorkerError):
    """The analysis provider failed to produce structured analysis."""


class WorkerTimeoutError(WorkerError):
    """The analysis provider exceeded its configured timeout."""


class WorkerEvidenceError(WorkerError):
    """The provider output was not grounded in the supplied sources."""


class WorkerResearchProvider(Protocol):
    """Provider-neutral interface for source-grounded worker analysis."""

    async def analyze(
        self,
        assignment: WorkerAssignment,
        evidence_candidates: list[EvidenceCandidate],
    ) -> WorkerAnalysis:
        """Select supplied evidence IDs without performing search or tool calls."""
        ...
