import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from research_agent.schemas import (
    EvidenceCandidate,
    SearchSource,
    WorkerAnalysis,
    WorkerAssignment,
    WorkerClaimSelection,
)
from research_agent.search.base import SearchProviderError, SearchTimeoutError
from research_agent.workers.base import (
    EmptySearchResultsError,
    WorkerEvidenceError,
    WorkerProviderError,
    WorkerTimeoutError,
)
from research_agent.workers.single_worker import SingleResearchWorker


def assignment() -> WorkerAssignment:
    return WorkerAssignment(
        worker_id="worker-7",
        focused_task="Assess adoption",
        investigation_focus="Investigate current production adoption",
        evidence_to_find=["Recent surveys", "Documented production cases"],
    )


def source(url: str = "https://example.com/report") -> SearchSource:
    return SearchSource(
        source_id="provider-id",
        title="Industry report",
        url=url,
        snippet="A survey found increased adoption.",
        publisher="Example Research",
    )


def analysis(evidence_id: str = "evidence-1") -> WorkerAnalysis:
    return WorkerAnalysis(
        claims=[
            WorkerClaimSelection(
                claim="Adoption increased.",
                evidence_ids=[evidence_id],
            )
        ],
        uncertainties=["The survey covers a limited sample."],
    )


class FakeSearch:
    def __init__(
        self,
        results: list[SearchSource] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = [source()] if results is None else results
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, *, limit: int) -> list[SearchSource]:
        self.calls.append((query, limit))
        if self.error:
            raise self.error
        return self.results


class FakeResearchProvider:
    def __init__(
        self,
        result: WorkerAnalysis | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.received_candidates: list[EvidenceCandidate] | None = None

    async def analyze(
        self,
        worker_assignment: WorkerAssignment,
        evidence_candidates: list[EvidenceCandidate],
    ) -> WorkerAnalysis:
        self.received_candidates = evidence_candidates
        if self.error:
            raise self.error
        return self.result or analysis(evidence_candidates[0].evidence_id)


def worker(
    search: Any | None = None,
    provider: Any | None = None,
) -> SingleResearchWorker:
    return SingleResearchWorker(
        search_provider=search or FakeSearch(),
        research_provider=provider or FakeResearchProvider(),
    )


def test_successful_research_is_grounded_and_preserves_worker_id() -> None:
    provider = FakeResearchProvider()
    result = asyncio.run(worker(provider=provider).research(assignment()))

    assert result.worker_id == "worker-7"
    assert result.assignment == assignment()
    assert result.claims[0].evidence[0].source_id == result.sources[0].source_id
    assert result.claims[0].evidence[0].evidence == result.sources[0].snippet
    assert provider.received_candidates is not None
    assert len(provider.received_candidates) == 1
    candidate = provider.received_candidates[0]
    assert candidate.evidence_id.startswith("evidence-")
    assert candidate.source_id == "source-1"
    assert str(candidate.source_url) == "https://example.com/report"
    assert candidate.evidence == "A survey found increased adoption."
    assert result.claims[0].evidence[0].evidence_id == candidate.evidence_id


def test_search_strategy_is_bounded_and_deduplicates_urls() -> None:
    search = FakeSearch(results=[source(), source()])

    result = asyncio.run(worker(search=search).research(assignment()))

    assert len(search.calls) == 2
    assert all(limit == 5 for _, limit in search.calls)
    assert len(result.sources) == 1


def test_worker_rejects_more_than_two_searches() -> None:
    with pytest.raises(ValueError, match="between 1 and 2"):
        SingleResearchWorker(
            search_provider=FakeSearch(),
            research_provider=FakeResearchProvider(),
            max_searches=3,
        )


def test_empty_search_results_are_rejected() -> None:
    with pytest.raises(EmptySearchResultsError):
        asyncio.run(worker(search=FakeSearch(results=[])).research(assignment()))


@pytest.mark.parametrize(
    "error",
    [SearchProviderError("failed"), SearchTimeoutError("timed out")],
)
def test_search_errors_are_preserved(error: Exception) -> None:
    with pytest.raises(type(error)):
        asyncio.run(worker(search=FakeSearch(error=error)).research(assignment()))


@pytest.mark.parametrize(
    "error",
    [WorkerProviderError("failed"), WorkerTimeoutError("timed out")],
)
def test_provider_errors_are_preserved(error: Exception) -> None:
    with pytest.raises(type(error)):
        asyncio.run(worker(provider=FakeResearchProvider(error=error)).research(assignment()))


def test_unknown_provider_evidence_id_is_rejected() -> None:
    provider = FakeResearchProvider(result=analysis("evidence-not-offered"))

    with pytest.raises(WorkerEvidenceError):
        asyncio.run(worker(provider=provider).research(assignment()))


def test_evidence_candidates_have_stable_ids_and_exact_source_chunks() -> None:
    long_snippet = "x" * 1_000 + "Exact second chunk."
    search = FakeSearch(
        results=[
            SearchSource(
                source_id="provider-id",
                title="Long report",
                url="https://example.com/long-report",
                snippet=long_snippet,
            )
        ]
    )
    first_run_provider = FakeResearchProvider()
    asyncio.run(worker(search=search, provider=first_run_provider).research(assignment()))
    assert first_run_provider.received_candidates is not None
    selected_id = first_run_provider.received_candidates[1].evidence_id
    provider = FakeResearchProvider(result=analysis(selected_id))

    result = asyncio.run(worker(search=search, provider=provider).research(assignment()))

    candidate_ids = [item.evidence_id for item in provider.received_candidates or []]
    assert len(candidate_ids) == 2
    assert len(set(candidate_ids)) == 2
    assert candidate_ids == [item.evidence_id for item in first_run_provider.received_candidates]
    assert result.claims[0].evidence[0].evidence == "Exact second chunk."
    assert result.claims[0].evidence[0].evidence in result.sources[0].snippet


def test_evidence_candidates_are_immutable() -> None:
    candidate = EvidenceCandidate(
        evidence_id="evidence-1",
        source_id="source-1",
        source_url="https://example.com/report",
        source_title="Report",
        evidence="Exact excerpt.",
    )

    with pytest.raises(ValidationError, match="frozen"):
        candidate.evidence = "Modified excerpt."


def test_duplicate_selected_evidence_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="evidence IDs within a claim must be unique"):
        WorkerClaimSelection(
            claim="Adoption increased.",
            evidence_ids=["evidence-1", "evidence-1"],
        )
