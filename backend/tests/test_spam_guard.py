"""Spam guards of POST /api/contact: per-IP rate limit and request body size limit.

Run against the contract's route with SMTP unconfigured (conftest's `settings`), so
no mail is ever involved.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from app import ratelimit
from app.body_limit import DEFAULT_MAX_BYTES, BodySizeLimitMiddleware

CONTACT = "/api/contact"
VALID_FORM = {
    "first_name": "Anna",
    "last_name": "Muster",
    "email": "anna@example.com",
    "message": "Ich interessiere mich für den EquiCube.",
    "website": "",
}
SECRET_MARKERS = ("Traceback", "smtp", "SMTP", "password", "Exception")


def _assert_detail_only(body: object) -> None:
    assert isinstance(body, dict)
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]
    for marker in SECRET_MARKERS:
        assert marker not in body["detail"]


def test_sixth_request_is_rate_limited_despite_changing_forwarded_for(
    client: TestClient,
) -> None:
    for i in range(ratelimit.MAX_REQUESTS):
        response = client.post(
            CONTACT, json=VALID_FORM, headers={"X-Forwarded-For": f"203.0.113.{i}"}
        )
        assert response.status_code != 429, f"request {i + 1} was rate limited"

    response = client.post(CONTACT, json=VALID_FORM, headers={"X-Forwarded-For": "198.51.100.77"})
    assert response.status_code == 429
    _assert_detail_only(response.json())
    assert int(response.headers["retry-after"]) > 0


def test_limit_frees_up_once_the_window_has_passed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1000.0]
    monkeypatch.setattr(ratelimit, "clock", lambda: now[0])
    for _ in range(ratelimit.MAX_REQUESTS):
        assert client.post(CONTACT, json=VALID_FORM).status_code != 429
    assert client.post(CONTACT, json=VALID_FORM).status_code == 429

    now[0] += ratelimit.WINDOW_SECONDS + 1
    assert client.post(CONTACT, json=VALID_FORM).status_code != 429


def test_expired_ips_are_dropped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [5000.0]
    monkeypatch.setattr(ratelimit, "clock", lambda: now[0])
    client.post(CONTACT, json=VALID_FORM)
    assert ratelimit.tracked_ips() == 1

    now[0] += ratelimit.WINDOW_SECONDS + 1
    other = TestClient(client.app, client=("192.0.2.10", 50000))
    other.post(CONTACT, json=VALID_FORM)
    # Only the fresh client is held; the expired one is gone.
    assert ratelimit.tracked_ips() == 1


def test_limit_is_per_connection_ip(client: TestClient) -> None:
    for _ in range(ratelimit.MAX_REQUESTS):
        client.post(CONTACT, json=VALID_FORM)
    assert client.post(CONTACT, json=VALID_FORM).status_code == 429

    other = TestClient(client.app, client=("192.0.2.20", 50000))
    assert other.post(CONTACT, json=VALID_FORM).status_code != 429


def test_reset_rate_limits_clears_the_record(client: TestClient) -> None:
    for _ in range(ratelimit.MAX_REQUESTS):
        client.post(CONTACT, json=VALID_FORM)
    ratelimit.reset_rate_limits()
    assert ratelimit.tracked_ips() == 0
    assert client.post(CONTACT, json=VALID_FORM).status_code != 429


def test_oversized_body_is_rejected_with_413(client: TestClient) -> None:
    form = dict(VALID_FORM, message="x" * 40 * 1024)
    response = client.post(CONTACT, json=form)
    assert response.status_code == 413
    _assert_detail_only(response.json())


def test_oversized_body_does_not_count_against_the_rate_limit(client: TestClient) -> None:
    big = dict(VALID_FORM, message="x" * 40 * 1024)
    for _ in range(ratelimit.MAX_REQUESTS + 2):
        assert client.post(CONTACT, json=big).status_code == 413
    assert client.post(CONTACT, json=VALID_FORM).status_code != 429


def test_body_within_limit_passes_the_middleware(client: TestClient) -> None:
    response = client.post(CONTACT, json=VALID_FORM)
    assert response.status_code not in (413, 429)


def _run_streaming(
    chunks: list[bytes], content_length: int | None, max_bytes: int
) -> tuple[list[Message], int]:
    """Drive the middleware directly with a body sent in chunks; count chunks read."""
    sent: list[Message] = []
    delivered = 0

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive() -> Message:
        nonlocal delivered
        chunk = chunks[delivered]
        delivered += 1
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": delivered < len(chunks),
        }

    async def send(message: Message) -> None:
        sent.append(message)

    headers = [] if content_length is None else [(b"content-length", str(content_length).encode())]
    scope: Scope = {"type": "http", "method": "POST", "path": CONTACT, "headers": headers}
    asyncio.run(BodySizeLimitMiddleware(inner, max_bytes=max_bytes)(scope, receive, send))
    return sent, delivered


def test_declared_content_length_over_limit_is_rejected_before_reading() -> None:
    sent, delivered = _run_streaming([b"x" * 10] * 5, content_length=50, max_bytes=20)
    assert delivered == 0
    assert sent[0]["status"] == 413
    _assert_detail_only(json.loads(sent[1]["body"]))


def test_streamed_body_is_cut_off_as_soon_as_it_exceeds_the_limit() -> None:
    sent, delivered = _run_streaming([b"x" * 10] * 10, content_length=None, max_bytes=25)
    # Rejected on the third chunk (30 bytes > 25); the remaining seven are never read.
    assert delivered == 3
    assert [m["type"] for m in sent] == ["http.response.start", "http.response.body"]
    assert sent[0]["status"] == 413
    _assert_detail_only(json.loads(sent[1]["body"]))


def test_streamed_body_within_limit_reaches_the_app() -> None:
    sent, delivered = _run_streaming(
        [b"x" * 10] * 3, content_length=30, max_bytes=DEFAULT_MAX_BYTES
    )
    assert delivered == 3
    assert sent[0]["status"] == 200
