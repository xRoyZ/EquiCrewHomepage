"""Error responses: every non-422 error is {"detail": "<short German text>"}.

No response ever carries a stack trace, raw exception text or configuration values;
unhandled exceptions are logged server-side and answered with a generic 500.
"""

from __future__ import annotations

import json
import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

INTERNAL_ERROR_DETAIL = "Interner Serverfehler. Bitte versuche es später erneut."

# German texts for errors the framework raises with its default English phrase.
_GERMAN_DETAILS: dict[int, str] = {
    400: "Ungültige Anfrage.",
    401: "Nicht angemeldet.",
    403: "Zugriff verweigert.",
    404: "Nicht gefunden.",
    405: "Methode nicht erlaubt.",
    413: "Anfrage zu groß.",
    429: "Zu viele Anfragen. Bitte versuche es später erneut.",
    500: INTERNAL_ERROR_DETAIL,
    501: "Noch nicht verfügbar.",
    503: "Dienst vorübergehend nicht verfügbar.",
}


def _fallback_detail(status_code: int) -> str:
    if status_code in _GERMAN_DETAILS:
        return _GERMAN_DETAILS[status_code]
    if status_code >= 500:
        return INTERNAL_ERROR_DETAIL
    return "Die Anfrage konnte nicht verarbeitet werden."


def _detail_for(exc: StarletteHTTPException) -> str:
    """The German detail of an HTTP error.

    A detail our own code raised is already a short German text and is kept; the
    framework's default English reason phrase (or any non-text detail) is replaced.
    """
    detail = exc.detail
    if isinstance(detail, str) and detail:
        try:
            default_phrase = HTTPStatus(exc.status_code).phrase
        except ValueError:
            default_phrase = None
        if detail != default_phrase:
            return detail
    return _fallback_detail(exc.status_code)


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return await _unhandled_exception_handler(request, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": _detail_for(exc)},
        headers=getattr(exc, "headers", None),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Only reached when an error escapes UnhandledErrorMiddleware (e.g. raised by an
    # outer middleware); the body is the same generic text.
    logger.error("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": INTERNAL_ERROR_DETAIL})


class UnhandledErrorMiddleware:
    """Turn any unhandled exception into the generic 500 body.

    Starlette sends the response of an `Exception` handler from its outermost
    layer, outside CORS, so the browser would receive a 500 without
    Access-Control-Allow-Origin and report a network error instead. This
    middleware sits inside the CORS layer and answers there.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception(
                "unhandled error on %s %s", scope.get("method", "?"), scope.get("path", "?")
            )
            if response_started:
                # Too late for a clean error body; let the server close the connection.
                raise
            body = json.dumps({"detail": INTERNAL_ERROR_DETAIL}, ensure_ascii=False).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})


def register_error_handlers(app: FastAPI) -> None:
    """Install the HTTP error handler, the 500 fallback and UnhandledErrorMiddleware.

    Call this before CORSMiddleware is added so the 500 body keeps its CORS headers.
    """
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
    app.add_middleware(UnhandledErrorMiddleware)
