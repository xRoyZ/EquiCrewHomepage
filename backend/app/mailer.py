"""Sends one contact form message by SMTP (standard library only)."""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import Settings

SMTP_SSL_PORT = 465
SMTP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class ContactData:
    """A validated contact submission (no CR/LF in names or e-mail, trimmed)."""

    first_name: str
    last_name: str
    email: str
    message: str


class MailNotConfiguredError(RuntimeError):
    """SMTP is not configured, so no mail can be sent."""


def build_contact_mail(settings: Settings, data: ContactData) -> EmailMessage:
    """The mail to the contact recipient: German subject, Reply-To the sender."""
    if not settings.smtp_from:
        raise MailNotConfiguredError("SMTP_FROM is not set")
    name = f"{data.first_name} {data.last_name}"
    mail = EmailMessage()
    mail["From"] = settings.smtp_from
    mail["To"] = settings.contact_recipient
    mail["Reply-To"] = data.email
    mail["Subject"] = f"Kontaktanfrage über die Website von {name}"
    mail.set_content(
        "Neue Nachricht über das Kontaktformular auf equicrew.com\n"
        "\n"
        f"Name: {name}\n"
        f"E-Mail: {data.email}\n"
        "\n"
        "Nachricht:\n"
        f"{data.message}\n"
    )
    return mail


def send_contact_mail(settings: Settings, data: ContactData) -> None:
    """Send exactly one mail to settings.contact_recipient.

    Port 465 uses implicit TLS (SMTP_SSL), every other port STARTTLS. Logs in only
    when both user and password are set. Raises MailNotConfiguredError without
    SMTP configuration and lets smtplib/OSError failures propagate to the caller.
    """
    if not settings.smtp_configured or not settings.smtp_host:
        raise MailNotConfiguredError("SMTP is not configured")
    mail = build_contact_mail(settings, data)
    context = ssl.create_default_context()

    smtp: smtplib.SMTP
    if settings.smtp_port == SMTP_SSL_PORT:
        smtp = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=SMTP_TIMEOUT_SECONDS,
            context=context,
        )
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS)

    with smtp as connection:
        if settings.smtp_port != SMTP_SSL_PORT:
            connection.starttls(context=context)
        if settings.smtp_user and settings.smtp_password:
            connection.login(settings.smtp_user, settings.smtp_password)
        connection.send_message(mail)
