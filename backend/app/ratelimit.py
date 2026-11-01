"""Per-client-IP rate limiting for POST /api/contact.

The client IP is the TCP peer address (request.client.host) only; X-Forwarded-For
is never read, so a changing header cannot get around the limit.

The record is an in-memory sliding window: for every IP the monotonic timestamps
of its accepted requests within the last WINDOW_SECONDS. Expired timestamps are
dropped on every check, and an IP without a timestamp left is removed entirely, so
no address is held longer than the window.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request

MAX_REQUESTS = 5
WINDOW_SECONDS = 600.0
RATE_LIMIT_DETAIL = "Zu viele Anfragen. Bitte versuche es später erneut."

# Monotonic clock; a module attribute so tests can move time forward.
clock: Callable[[], float] = time.monotonic

_lock = threading.Lock()
_requests: dict[str, deque[float]] = {}


def client_ip(request: Request) -> str:
    """The connection's peer address; never taken from a request header."""
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _drop_expired(now: float) -> None:
    """Remove timestamps older than the window, and IPs with none left (lock held)."""
    cutoff = now - WINDOW_SECONDS
    for ip in list(_requests):
        stamps = _requests[ip]
        while stamps and stamps[0] <= cutoff:
            stamps.popleft()
        if not stamps:
            del _requests[ip]


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency: raise HTTPException(429) when the client is over the limit.

    At most MAX_REQUESTS accepted requests per client IP within WINDOW_SECONDS; a
    rejected request is not recorded, so the client is free again once its oldest
    accepted request leaves the window.
    """
    ip = client_ip(request)
    with _lock:
        now = clock()
        _drop_expired(now)
        stamps = _requests.get(ip)
        if stamps is not None and len(stamps) >= MAX_REQUESTS:
            retry_after = max(1, int(stamps[0] + WINDOW_SECONDS - now) + 1)
            raise HTTPException(
                status_code=429,
                detail=RATE_LIMIT_DETAIL,
                headers={"Retry-After": str(retry_after)},
            )
        if stamps is None:
            stamps = deque()
            _requests[ip] = stamps
        stamps.append(now)


def tracked_ips() -> int:
    """How many client IPs the record currently holds."""
    with _lock:
        return len(_requests)


def reset_rate_limits() -> None:
    """Forget all recorded requests (used by the test suite between tests)."""
    with _lock:
        _requests.clear()
