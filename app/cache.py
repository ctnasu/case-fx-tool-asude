import asyncio
from datetime import date as date_cls
from decimal import Decimal
from typing import Awaitable, Callable, Dict, NamedTuple, Tuple

CacheKey = Tuple[str, str, date_cls]


class CacheEntry(NamedTuple):
    rate: Decimal
    rate_date: date_cls
    cached_on: date_cls  # the UTC calendar day this entry was fetched


class RateCache:
    """In-memory cache for (base, target, asked_date) -> (rate, rate_date).

    A published historical rate never changes, so those entries are kept
    forever. An asked_date of "today" is different: the ECB publishes once
    a day, so a rate fetched for today is only trusted for the rest of that
    same UTC day — a long-running process shouldn't keep serving the rate
    it saw at startup as "today's rate" a week later.

    Concurrent requests for the same uncached key share one asyncio.Lock
    instead of each calling upstream: the first caller fetches, the rest
    wait on the lock and then find the entry already there. Without this,
    the cache is shared mutable state with no coordination between
    coroutines racing to fill it — the same class of bug the graph-node
    state sharing in my thesis project caused, just in a smaller shape.
    """

    def __init__(self) -> None:
        self._entries: Dict[CacheKey, CacheEntry] = {}
        self._locks: Dict[CacheKey, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    @staticmethod
    def _is_fresh(entry: CacheEntry, asked_date: date_cls, today: date_cls) -> bool:
        if asked_date != today:
            return True
        return entry.cached_on == today

    async def get_or_fetch(
        self,
        base: str,
        target: str,
        asked_date: date_cls,
        today: date_cls,
        fetch: Callable[[], Awaitable[Tuple[Decimal, date_cls]]],
    ) -> Tuple[Decimal, date_cls]:
        key = (base, target, asked_date)

        cached = self._entries.get(key)
        if cached is not None and self._is_fresh(cached, asked_date, today):
            return cached.rate, cached.rate_date

        async with self._locks_guard:
            lock = self._locks.setdefault(key, asyncio.Lock())

        async with lock:
            # Re-check: another coroutine may have populated this key while
            # we were waiting for the lock.
            cached = self._entries.get(key)
            if cached is not None and self._is_fresh(cached, asked_date, today):
                return cached.rate, cached.rate_date

            rate, rate_date = await fetch()
            self._entries[key] = CacheEntry(rate=rate, rate_date=rate_date, cached_on=today)
            return rate, rate_date
