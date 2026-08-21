import asyncio
import json

import httpx
import pytest

from research_agent.search.base import SearchProviderError, SearchTimeoutError
from research_agent.search.tavily import TAVILY_SEARCH_URL, TavilySearchProvider


def provider_with(handler) -> TavilySearchProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TavilySearchProvider(
        api_key="test-key",
        timeout_seconds=1,
        client=client,
    )


def test_basic_search_preserves_source_provenance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == TAVILY_SEARCH_URL
        assert request.headers["Authorization"] == "Bearer test-key"
        assert payload["search_depth"] == "basic"
        assert payload["max_results"] == 5
        assert payload["include_answer"] is False
        assert payload["include_raw_content"] is False
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Primary source",
                        "url": "https://example.com/report",
                        "content": "The report documents the measured result.",
                    }
                ]
            },
        )

    sources = asyncio.run(provider_with(handler).search("focused query", limit=5))

    assert len(sources) == 1
    assert sources[0].title == "Primary source"
    assert str(sources[0].url) == "https://example.com/report"
    assert sources[0].snippet == "The report documents the measured result."


def test_empty_results_are_returned_cleanly() -> None:
    provider = provider_with(lambda request: httpx.Response(200, json={"results": []}))

    assert asyncio.run(provider.search("focused query", limit=5)) == []


def test_duplicate_and_invalid_results_are_filtered() -> None:
    results = [
        {"title": "Valid", "url": "https://example.com/a", "content": "Evidence A"},
        {"title": "Duplicate", "url": "https://example.com/a", "content": "Evidence B"},
        {"title": "Invalid URL", "url": "not-a-url", "content": "Evidence C"},
        {"title": "Missing content", "url": "https://example.com/d", "content": ""},
    ]
    provider = provider_with(
        lambda request: httpx.Response(200, json={"results": results})
    )

    sources = asyncio.run(provider.search("focused query", limit=5))

    assert [str(source.url) for source in sources] == ["https://example.com/a"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"unexpected": []}),
        httpx.Response(200, content=b"not-json"),
    ],
)
def test_malformed_response_is_normalized(response: httpx.Response) -> None:
    provider = provider_with(lambda request: response)

    with pytest.raises(SearchProviderError):
        asyncio.run(provider.search("focused query", limit=5))


def test_http_failure_is_normalized() -> None:
    provider = provider_with(lambda request: httpx.Response(503))

    with pytest.raises(SearchProviderError):
        asyncio.run(provider.search("focused query", limit=5))


def test_timeout_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(SearchTimeoutError):
        asyncio.run(provider_with(handler).search("focused query", limit=5))


@pytest.mark.parametrize(("query", "limit"), [("   ", 5), ("query", 0), ("query", 11)])
def test_invalid_search_arguments_are_rejected(query: str, limit: int) -> None:
    provider = provider_with(lambda request: httpx.Response(200, json={"results": []}))

    with pytest.raises(ValueError):
        asyncio.run(provider.search(query, limit=limit))
