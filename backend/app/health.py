"""GET /api/health - liveness probe; answers 200 also without any SMTP_* set."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter()


@router.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Report that the service is up.

    It resolves the same settings dependency the contact route uses, so a broken
    configuration shows here and not only on the first real request. Missing SMTP
    settings are not an error: the contact route then answers 503.
    """
    del settings  # resolved for the check above; its values are never exposed
    return {"status": "ok"}
