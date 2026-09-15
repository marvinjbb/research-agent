from typing import Any

import httpx
from pydantic import ValidationError

from research_agent.observability import log_event
from research_agent.schemas import SearchSource
from research_agent.search.base import SearchProviderError, SearchTimeoutError

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilySearchProvider:
    """Bounded Basic Search adapter for Tavily's HTTP API."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def search(self, query: str, *, limit: int) -> list[SearchSource]:
        if not query.strip():
            raise ValueError("search query must not be blank")
        if not 1 <= limit <= 10:
            raise ValueError("search result limit must be between 1 and 10")

        if self._client is not None:
            return await self._search_with(self._client, query, limit)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            return await self._search_with(client, query, limit)

    async def _search_with(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
    ) -> list[SearchSource]:
        try:
            response = await client.post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": limit,
                    "include_answer": False,
                    "include_images": False,
                    "include_raw_content": False,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            log_event(
                "provider_call_failed",
                component="tavily_search",
                error_category="timeout",
            )
            raise SearchTimeoutError("Tavily search timed out") from exc
        except (httpx.HTTPError, ValueError) as exc:
            log_event(
                "provider_call_failed",
                component="tavily_search",
                error_category="provider_failure",
            )
            raise SearchProviderError("Tavily search failed") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            log_event(
                "provider_call_failed",
                component="tavily_search",
                error_category="malformed_response",
            )
            raise SearchProviderError("Tavily returned a malformed response")

        sources = self._normalize_results(payload["results"], limit)
        log_event(
            "provider_call_completed",
            component="tavily_search",
            outcome="succeeded",
            source_count=len(sources),
        )
        return sources

    def _normalize_results(
        self,
        results: list[Any],
        limit: int,
    ) -> list[SearchSource]:
        sources: list[SearchSource] = []
        seen_urls: set[str] = set()
        for result in results:
            if not isinstance(result, dict):
                continue
            try:
                source = SearchSource(
                    source_id=f"tavily-{len(sources) + 1}",
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content", ""),
                )
            except ValidationError:
                continue
            canonical_url = str(source.url)
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            sources.append(source)
            if len(sources) == limit:
                break
        return sources
