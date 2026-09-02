import pytest

from app.main import _cache


@pytest.fixture(autouse=True)
def reset_cache():
    """The rate cache is a module-level singleton so it survives across a
    process's lifetime the way it would in production — but that means
    tests must not leak cached entries into each other."""
    _cache._entries.clear()
    _cache._locks.clear()
    yield
    _cache._entries.clear()
    _cache._locks.clear()
