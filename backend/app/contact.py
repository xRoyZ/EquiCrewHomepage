"""POST /api/contact - sends a contact form message by e-mail."""

from __future__ import annotations

import logging
import smtplib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, BeforeValidator, EmailStr, Field, StringConstraints

from app.config import Settings, get_settings
from app.mailer import ContactData, MailNotConfiguredError, send_contact_mail
from app.ratelimit import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

NOT_CONFIGURED_DETAIL = (
    "Der Versand ist derzeit nicht möglich. Bitte schreib uns direkt an office@equicrew.com."
)
SEND_FAILED_DETAIL = (
    "Deine Nachricht konnte nicht gesendet werden. "
    "Bitte versuche es später erneut oder schreib uns an office@equicrew.com."
)

MAX_EMAIL_LENGTH = 254
# CR and LF, plus every other character str.splitlines() and the e-mail header
# folding treat as a line break, so no user value can start a new mail header.
_LINE_BREAKS = frozenset("\r\n\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029")


def _single_line(value: object) -> object:
    """Reject line breaks (before trimming, so a trailing newline is caught too)."""
    if isinstance(value, str) and any(char in _LINE_BREAKS for char in value):
        raise ValueError("darf keinen Zeilenumbruch enthalten")
    return value


SingleLineName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    BeforeValidator(_single_line),
]


def _email_text(value: object) -> object:
    """Reject line breaks, trim, and cap the address at 254 characters."""
    value = _single_line(value)
    if isinstance(value, str):
        value = value.strip()
        if len(value) > MAX_EMAIL_LENGTH:
            raise ValueError("ist zu lang")
    return value


SingleLineEmail = Annotated[EmailStr, BeforeValidator(_email_text)]
MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class ContactRequest(BaseModel):
    """The contact form as the frontend posts it."""

    first_name: SingleLineName
    last_name: SingleLineName
    email: SingleLineEmail
    message: MessageText
    website: str = Field(default="", description="Honeypot - must stay empty")


@router.post("/api/contact")
def send_contact(
    payload: ContactRequest,
    _rate_limit: None = Depends(enforce_rate_limit),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Validate the form, send it to the contact recipient, answer {"status": "sent"}."""
    if payload.website.strip():
        # A bot filled the hidden field: answer like a success, send nothing.
        logger.info("contact submission discarded (honeypot)")
        return {"status": "sent"}

    if not settings.smtp_configured:
        logger.warning("contact submission rejected: SMTP not configured")
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_DETAIL)

    data = ContactData(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        message=payload.message,
    )
    try:
        send_contact_mail(settings, data)
    except MailNotConfiguredError:
        logger.warning("contact submission rejected: SMTP not configured")
        raise HTTPException(status_code=503, detail=NOT_CONFIGURED_DETAIL) from None
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        # Only the error class: no message content, no SMTP host/user/password.
        logger.warning("contact mail could not be sent (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail=SEND_FAILED_DETAIL) from None

    logger.info("contact submission accepted and sent")
    return {"status": "sent"}
