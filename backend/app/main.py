"""FastAPI application factory for the EquiCrew contact backend.

Start: `uvicorn app.main:app` from inside backend/.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import contact, health
from app.body_limit import DEFAULT_MAX_BYTES, BodySizeLimitMiddleware
from app.config import Settings, get_settings
from app.errors import register_error_handlers

logger = logging.getLogger(__name__)


def _resolve_settings(app: FastAPI) -> Settings:
    """The settings the routes will see, honouring a test's dependency override."""
    provider = app.dependency_overrides.get(get_settings, get_settings)
    return provider()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Validate the configuration once at startup. Missing SMTP settings are not
    # fatal (the contact route answers 503); only whether they are set is logged,
    # never their values.
    settings = _resolve_settings(app)
    if settings.smtp_configured:
        logger.info("SMTP configured - contact messages go to the configured recipient")
    else:
        logger.warning(
            "SMTP not configured (SMTP_HOST, SMTP_PORT, SMTP_FROM) - POST /api/contact answers 503"
        )
    if not settings.frontend_origin:
        logger.info("FRONTEND_ORIGIN not set - no cross-origin requests are allowed")
    yield


def create_app() -> FastAPI:
    """Build the application with its middleware, error handlers and routers."""
    settings = get_settings()
    app = FastAPI(title="EquiCrew Kontakt-API", lifespan=_lifespan)

    # Order matters: the middleware added last is the outermost. CORS wraps the
    # error middleware so even a 500 or a 413 carries the CORS headers.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=DEFAULT_MAX_BYTES)
    register_error_handlers(app)
    if settings.frontend_origin:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[settings.frontend_origin],
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    app.include_router(health.router)
    app.include_router(contact.router)
    return app


app = create_app()
