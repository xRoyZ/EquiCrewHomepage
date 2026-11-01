"""POST /api/contact - sends a contact form message by e-mail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.ratelimit import enforce_rate_limit

router = APIRouter()


@router.post("/api/contact")
def send_contact(
    _rate_limit: None = Depends(enforce_rate_limit),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Validate the form, send it to the contact recipient, answer {"status": "sent"}.

    Placeholder until the contact ticket (#9) fills it.
    """
    del settings
    raise HTTPException(
        status_code=501,
        detail="Der Versand über das Kontaktformular ist noch nicht verfügbar.",
    )
