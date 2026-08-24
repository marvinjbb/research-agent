import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from time import monotonic

from fastapi import HTTPException, status

from research_agent.config import PublicApiSettings


class PublicResearchLimiter:
    """Bound one process's public research cost and concurrent provider work."""

    def __init__(
        self,
        *,
        request_limit: int,
        window_seconds: int,
        max_concurrent: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._request_limit = request_limit
        self._window_seconds = window_seconds
        self._max_concurrent = max_concurrent
        self._clock = clock
        self._accepted_at: deque[float] = deque()
        self._active = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            cutoff = now - self._window_seconds
            while self._accepted_at and self._accepted_at[0] <= cutoff:
                self._accepted_at.popleft()

            if self._active >= self._max_concurrent:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="research service is currently at capacity",
                    headers={"Retry-After": "5"},
                )
            if len(self._accepted_at) >= self._request_limit:
                retry_after = max(1, int(self._accepted_at[0] + self._window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="public research request limit reached",
                    headers={"Retry-After": str(retry_after)},
                )

            self._accepted_at.append(now)
            self._active += 1

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)

    async def reset(self) -> None:
        """Reset process-local state for isolated tests."""
        async with self._lock:
            self._accepted_at.clear()
            self._active = 0


public_api_settings = PublicApiSettings()
public_research_limiter = PublicResearchLimiter(
    request_limit=public_api_settings.research_rate_limit_requests,
    window_seconds=public_api_settings.research_rate_limit_window_seconds,
    max_concurrent=public_api_settings.research_max_concurrent,
)


async def enforce_public_research_limit() -> AsyncIterator[None]:
    """Reserve and reliably release one bounded public workflow slot."""
    await public_research_limiter.acquire()
    try:
        yield
    finally:
        await public_research_limiter.release()
