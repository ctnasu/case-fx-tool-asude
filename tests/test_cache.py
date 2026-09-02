import asyncio
from datetime import date
from decimal import Decimal

from app.cache import RateCache


def test_concurrent_requests_for_same_key_fetch_upstream_once():
    """Ten coroutines ask for the same (base, target, date) at once, before
    any of them has a chance to populate the cache. Without the per-key
    lock, every one of them would race past the "is it cached?" check and
    call upstream — this is the thundering-herd bug the lock exists to
    prevent."""
    cache = RateCache()
    calls = {"count": 0}

    async def fetch():
        calls["count"] += 1
        await asyncio.sleep(0.02)  # stand in for upstream latency
        return Decimal("47.0"), date(2026, 8, 28)

    async def run_concurrently():
        return await asyncio.gather(
            *[cache.get_or_fetch("EUR", "TRY", date(2026, 8, 28), fetch) for _ in range(10)]
        )

    results = asyncio.run(run_concurrently())

    assert calls["count"] == 1
    assert all(result == (Decimal("47.0"), date(2026, 8, 28)) for result in results)


def test_repeat_query_does_not_refetch():
    cache = RateCache()
    calls = {"count": 0}

    async def fetch():
        calls["count"] += 1
        return Decimal("47.0"), date(2026, 8, 28)

    async def run():
        await cache.get_or_fetch("EUR", "TRY", date(2026, 8, 28), fetch)
        await cache.get_or_fetch("EUR", "TRY", date(2026, 8, 28), fetch)

    asyncio.run(run())

    assert calls["count"] == 1


def test_different_dates_are_different_cache_entries():
    cache = RateCache()
    calls = {"count": 0}

    async def fetch():
        calls["count"] += 1
        return Decimal("47.0"), date(2026, 8, 28)

    async def run():
        await cache.get_or_fetch("EUR", "TRY", date(2026, 8, 28), fetch)
        await cache.get_or_fetch("EUR", "TRY", date(2026, 8, 29), fetch)

    asyncio.run(run())

    assert calls["count"] == 2
