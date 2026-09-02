import asyncio
from datetime import date as date_cls
from decimal import Decimal
from typing import Awaitable, Callable, Dict, NamedTuple, Tuple

CacheKey = Tuple[str, str, date_cls]


class CacheEntry(NamedTuple):
    rate: Decimal
    rate_date: date_cls


class RateCache:
    """In-memory cache for (base, target, asked_date) -> (rate, rate_date).

    Keyed on the asked date, not just cached forever globally, so a
    historical lookup and "today"'s lookup never collide. A published rate
    for a past date never changes, so every entry is kept for the process's
    lifetime — including "today"'s, once fetched. (A prior version tried to
    expire "today" entries at day rollover; on inspection that check could
    never actually fire, since a date that stops being "today" is from then
    on treated as historical and short-circuits before the check runs. The
    real staleness risk is intra-day — ECB publishes once, so an early
    fetch could be reused after a later publish — but catching that needs a
    wall-clock TTL tied to their publish schedule, which felt like scope
    creep here. Simpler to say plainly what this does: caches per exact
    date asked, for as long as the process runs.)

    Concurrent requests for the same uncached key share one asyncio.Lock
    instead of each calling upstream: the first caller fetches, the rest
    wait on the lock and then find the entry already there. Locks are
    created lazily, inside the running event loop — creating one eagerly in
    __init__ binds it to whatever loop happens to be current (or none) at
    construction time, which breaks under Python's own asyncio.run().
    """

    def __init__(self) -> None:
        self._entries: Dict[CacheKey, CacheEntry] = {}
        self._locks: Dict[CacheKey, asyncio.Lock] = {}

    async def get_or_fetch(
        self,
        base: str,
        target: str,
        asked_date: date_cls,
        fetch: Callable[[], Awaitable[Tuple[Decimal, date_cls]]],
    ) -> Tuple[Decimal, date_cls]:
        key = (base, target, asked_date)

        cached = self._entries.get(key)
        if cached is not None:
            return cached.rate, cached.rate_date

        # Plain dict.setdefault, not a separate guard lock: asyncio is
        # single-threaded and cooperative, so nothing can interleave
        # between the .get() above and this line — there's no await in
        # between for another coroutine to run during.
        lock = self._locks.setdefault(key, asyncio.Lock())

        async with lock:
            # Another coroutine may have populated this key while we were
            # waiting for the lock.
            cached = self._entries.get(key)
            if cached is not None:
                return cached.rate, cached.rate_date

            rate, rate_date = await fetch()
            self._entries[key] = CacheEntry(rate=rate, rate_date=rate_date)
            return rate, rate_date
