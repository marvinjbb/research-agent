from typing import Protocol

from research_agent.schemas import SearchSource


class SearchError(Exception):
    """Base error raised by a search provider."""


class SearchProviderError(SearchError):
    """The search provider failed to return results."""


class SearchTimeoutError(SearchError):
    """The search provider exceeded its configured timeout."""


class SearchProvider(Protocol):
    """Provider-neutral interface for one bounded web search."""

    async def search(self, query: str, *, limit: int) -> list[SearchSource]:
        """Return normalized sources for one focused query."""
        ...
