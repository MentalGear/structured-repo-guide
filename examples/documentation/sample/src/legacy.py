"""Debt that predates the checks: the baseline records it, and it can only shrink."""

# Previously this module kept one global dict; we now keep one cache per request.
# Fixed on 2025-01-14 in commit 3fa9c21 after the outage.
# See docs/research/cache-notes.md and backlog 99 for the numbers.
def old_cache():
    return {}
