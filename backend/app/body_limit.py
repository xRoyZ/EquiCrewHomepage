"""ASGI middleware that caps the request body size."""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

DEFAULT_MAX_BYTES = 32768


class BodySizeLimitMiddleware:
    """Reject request bodies larger than `max_bytes` with 413.

    Placeholder until the body-limit ticket (#10) fills it: passes every request
    through unchanged.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)
