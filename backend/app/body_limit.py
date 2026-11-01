"""ASGI middleware that caps the request body size."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_MAX_BYTES = 32768
TOO_LARGE_DETAIL = "Die Anfrage ist zu groß."


class BodySizeLimitMiddleware:
    """Reject request bodies larger than `max_bytes` with 413 {"detail": ...}.

    A declared Content-Length over the limit is refused before the body is read at
    all. Without one (or when it understates the body), the received bytes are
    counted chunk by chunk and the request is refused as soon as they exceed the
    limit, so a large body is never held in memory in full.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _send_too_large(send)
            return

        received = 0
        response_started = False
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    if not response_started:
                        await _send_too_large(send)
                    # The app sees a closed connection and stops reading.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if rejected:
                # The 413 has been sent; whatever the app answers is discarded.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            # Once the 413 is out, the app's reaction to the cut-off body (e.g.
            # Starlette's ClientDisconnect) is expected and has nobody to answer.
            if not rejected:
                raise


def _content_length(scope: Scope) -> int | None:
    """The declared Content-Length, or None when absent or not a number."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _send_too_large(send: Send) -> None:
    body = json.dumps({"detail": TOO_LARGE_DETAIL}, ensure_ascii=False).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
