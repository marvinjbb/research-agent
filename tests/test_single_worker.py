import asyncio
from typing import Any

import pytest

from research_agent.schemas import (
    ClaimEvidence,
    SearchSource,
    WorkerAnalysis,
    WorkerAssignment,
    WorkerClaim,
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


def analysis(source_id: str = "source-1") -> WorkerAnalysis:
    return WorkerAnalysis(
        claims=[
            WorkerClaim(
                claim="Adoption increased.",
                evidence=[
                    ClaimEvidence(
                        source_id=source_id,
                        evidence="A survey found increased adoption.",
                    )
                ],
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
        self.result = analysis() if result is None else result
        self.error = error

    async def analyze(
        self,
        worker_assignment: WorkerAssignment,
        sources: list[SearchSource],
    ) -> WorkerAnalysis:
        if self.error:
            raise self.error
        return self.result


def worker(
    search: Any | None = None,
    provider: Any | None = None,
) -> SingleResearchWorker:
    return SingleResearchWorker(
        search_provider=search or FakeSearch(),
        research_provider=provider or FakeResearchProvider(),
    )


def test_successful_research_is_grounded_and_preserves_worker_id() -> None:
    result = asyncio.run(worker().research(assignment()))

    assert result.worker_id == "worker-7"
    assert result.assignment == assignment()
    assert result.claims[0].evidence[0].source_id == result.sources[0].source_id


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
        asyncio.run(
            worker(provider=FakeResearchProvider(error=error)).research(assignment())
        )


def test_unsupported_provider_evidence_is_rejected() -> None:
    provider = FakeResearchProvider(result=analysis("source-not-returned"))

    with pytest.raises(WorkerEvidenceError):
        asyncio.run(worker(provider=provider).research(assignment()))
