import asyncio
from collections.abc import Iterator

import pytest

from research_agent.public_api import public_research_limiter


@pytest.fixture(autouse=True)
def reset_public_research_limit() -> Iterator[None]:
    """Keep the process-global production limiter isolated between tests."""
    asyncio.run(public_research_limiter.reset())
    yield
    asyncio.run(public_research_limiter.reset())
