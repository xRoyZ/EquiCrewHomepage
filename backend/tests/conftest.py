"""Shared fixtures for the backend test suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.ratelimit import reset_rate_limits


@pytest.fixture
def settings() -> Settings:
    """Settings the `client` fixture serves; SMTP unconfigured by default.

    A test module that needs SMTP configured redefines this fixture.
    """
    return Settings(
        smtp_host=None,
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
        smtp_from=None,
        contact_recipient="office@equicrew.com",
        frontend_origin=None,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """TestClient on create_app() with get_settings overridden; runs the lifespan."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Iterator[None]:
    """Every test starts with an empty rate-limit record."""
    reset_rate_limits()
    yield
    reset_rate_limits()
