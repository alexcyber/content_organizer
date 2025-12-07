"""
Pytest configuration and fixtures.
"""

import pytest


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache before each test."""
    from utils.cache import SimpleCache
    cache = SimpleCache()
    cache.clear()
    yield
    cache.clear()
