"""Tests for the backend skeleton: health route, route table, config, errors, CORS."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

from app.config import Settings, get_settings
from app.errors import INTERNAL_ERROR_DETAIL
from app.main import create_app

SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")
ORIGIN = "http://127.0.0.1:5500"


@pytest.fixture
def no_smtp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (*SMTP_VARS, "CONTACT_RECIPIENT", "FRONTEND_ORIGIN"):
        monkeypatch.delenv(name, raising=False)


def _walk(routes: list[BaseRoute]) -> Iterator[APIRoute]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        # Recent FastAPI keeps an included router as one entry pointing at it;
        # the routers here carry no prefix, so their paths are already the full ones.
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _walk(included.routes)


def _routes(app: FastAPI) -> set[tuple[str, str]]:
    """(path, method) of every API route in the app's route table."""
    return {(route.path, method) for route in _walk(app.routes) for method in route.methods}


# --- health -------------------------------------------------------------------


def test_health_ok_without_any_smtp_env(no_smtp_env: None) -> None:
    # The real start path: no dependency override, lifespan runs.
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ok_through_client_fixture(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routes_registered_in_route_table(no_smtp_env: None) -> None:
    routes = _routes(create_app())
    assert ("/api/health", "GET") in routes
    assert ("/api/contact", "POST") in routes


def test_module_level_app_is_wired() -> None:
    from app.main import app

    routes = _routes(app)
    assert ("/api/health", "GET") in routes
    assert ("/api/contact", "POST") in routes


# --- config -------------------------------------------------------------------


def test_settings_defaults_without_env(no_smtp_env: None) -> None:
    settings = get_settings()
    assert settings.smtp_host is None
    assert settings.smtp_from is None
    assert settings.contact_recipient == "office@equicrew.com"
    assert settings.frontend_origin is None
    assert settings.smtp_configured is False


def test_settings_read_from_env(no_smtp_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "mail.example.test")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw-from-test")
    monkeypatch.setenv("SMTP_FROM", "website@example.test")
    monkeypatch.setenv("CONTACT_RECIPIENT", "inbox@example.test")
    monkeypatch.setenv("FRONTEND_ORIGIN", ORIGIN)
    settings = get_settings()
    assert settings.smtp_host == "mail.example.test"
    assert settings.smtp_port == 2525
    assert settings.smtp_user == "user"
    assert settings.smtp_password == "pw-from-test"
    assert settings.smtp_from == "website@example.test"
    assert settings.contact_recipient == "inbox@example.test"
    assert settings.frontend_origin == ORIGIN
    assert settings.smtp_configured is True
    assert "pw-from-test" not in repr(settings)


@pytest.mark.parametrize(
    ("host", "port", "sender", "expected"),
    [
        ("mail.example.test", 587, "website@example.test", True),
        (None, 587, "website@example.test", False),
        ("mail.example.test", 587, None, False),
        ("mail.example.test", 0, "website@example.test", False),
    ],
)
def test_smtp_configured_needs_host_port_and_from(
    host: str | None, port: int, sender: str | None, expected: bool
) -> None:
    settings = Settings(smtp_host=host, smtp_port=port, smtp_from=sender)
    assert settings.smtp_configured is expected


def test_invalid_smtp_port_disables_smtp_instead_of_crashing(
    no_smtp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SMTP_HOST", "mail.example.test")
    monkeypatch.setenv("SMTP_FROM", "website@example.test")
    monkeypatch.setenv("SMTP_PORT", "not-a-port")
    assert get_settings().smtp_configured is False


# --- error bodies -------------------------------------------------------------


def _app_with_failing_route(monkeypatch: pytest.MonkeyPatch, origin: str | None) -> TestClient:
    for name in SMTP_VARS:
        monkeypatch.delenv(name, raising=False)
    if origin:
        monkeypatch.setenv("FRONTEND_ORIGIN", origin)
    else:
        monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)
    app = create_app()

    @app.get("/api/_boom")
    def boom() -> None:
        raise RuntimeError("smtp.internal.test user=secret-user password=secret-pw")

    return TestClient(app)


def test_unhandled_exception_gives_generic_german_500(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app_with_failing_route(monkeypatch, ORIGIN)
    response = client.get("/api/_boom", headers={"Origin": ORIGIN})
    assert response.status_code == 500
    assert response.json() == {"detail": INTERNAL_ERROR_DETAIL}
    for leaked in ("RuntimeError", "smtp.internal.test", "secret-user", "secret-pw", "Traceback"):
        assert leaked not in response.text
    # The error is answered inside the CORS layer, so the browser can read it.
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_unknown_route_gives_german_detail(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Nicht gefunden."}


def test_wrong_method_keeps_detail_convention(client: TestClient) -> None:
    response = client.get("/api/contact")
    assert response.status_code == 405
    assert set(response.json()) == {"detail"}
    assert response.json()["detail"] != "Method Not Allowed"


# --- CORS ---------------------------------------------------------------------


def test_cors_allows_only_frontend_origin(
    no_smtp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", ORIGIN)
    with TestClient(create_app()) as client:
        allowed = client.options(
            "/api/contact",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"},
        )
        other = client.get("/api/health", headers={"Origin": "http://evil.example.test"})
    assert allowed.headers.get("access-control-allow-origin") == ORIGIN
    assert "access-control-allow-origin" not in other.headers


def test_no_cors_when_frontend_origin_unset(no_smtp_env: None) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
