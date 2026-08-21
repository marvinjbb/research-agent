from pydantic import ValidationError

from research_agent.schemas import SearchSource, WorkerAssignment, WorkerResult
from research_agent.search.base import SearchProvider
from research_agent.workers.base import (
    EmptySearchResultsError,
    WorkerEvidenceError,
    WorkerResearchProvider,
)


class SingleResearchWorker:
    """Run one assignment with a fixed, non-recursive search strategy."""

    def __init__(
        self,
        *,
        search_provider: SearchProvider,
        research_provider: WorkerResearchProvider,
        max_searches: int = 2,
        results_per_search: int = 5,
    ) -> None:
        if not 1 <= max_searches <= 2:
            raise ValueError("max_searches must be between 1 and 2")
        if not 1 <= results_per_search <= 10:
            raise ValueError("results_per_search must be between 1 and 10")
        self._search_provider = search_provider
        self._research_provider = research_provider
        self._max_searches = max_searches
        self._results_per_search = results_per_search

    async def research(self, assignment: WorkerAssignment) -> WorkerResult:
        sources_by_url: dict[str, SearchSource] = {}
        for query in self._queries_for(assignment):
            results = await self._search_provider.search(
                query,
                limit=self._results_per_search,
            )
            for source in results:
                canonical_url = str(source.url)
                if canonical_url not in sources_by_url and len(sources_by_url) < 10:
                    source_data = source.model_dump()
                    source_data["source_id"] = f"source-{len(sources_by_url) + 1}"
                    sources_by_url[canonical_url] = SearchSource.model_validate(source_data)

        sources = list(sources_by_url.values())
        if not sources:
            raise EmptySearchResultsError("search returned no usable sources")

        analysis = await self._research_provider.analyze(assignment, sources)
        try:
            return WorkerResult.model_validate(
                {
                    "worker_id": assignment.worker_id,
                    "assignment": assignment,
                    "claims": analysis.claims,
                    "sources": sources,
                    "uncertainties": analysis.uncertainties,
                }
            )
        except ValidationError as exc:
            raise WorkerEvidenceError("worker analysis contains unsupported evidence") from exc

    def _queries_for(self, assignment: WorkerAssignment) -> list[str]:
        queries = [f"{assignment.focused_task} {assignment.investigation_focus}"]
        evidence_query = " ".join(assignment.evidence_to_find)
        if self._max_searches > 1 and evidence_query:
            queries.append(f"{assignment.focused_task} {evidence_query}")
        return queries[: self._max_searches]
