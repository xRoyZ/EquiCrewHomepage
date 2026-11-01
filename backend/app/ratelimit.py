"""Per-client-IP rate limiting for POST /api/contact.

The client IP is the TCP peer address (request.client.host) only; X-Forwarded-For
is never read, so a changing header cannot get around the limit.
"""

from __future__ import annotations

from fastapi import Request


def client_ip(request: Request) -> str:
    """The connection's peer address; never taken from a request header."""
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency: raise HTTPException(429) when the client is over the limit.

    Placeholder until the rate-limit ticket (#10) fills it: lets every request pass.
    """
    del request


def reset_rate_limits() -> None:
    """Forget all recorded requests (used by the test suite between tests)."""
