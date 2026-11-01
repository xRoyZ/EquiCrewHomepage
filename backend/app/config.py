"""Runtime configuration, read from the environment.

Nothing here is read at import time: `get_settings()` reads the environment each
time it is called, so the process always boots - even without any SMTP_* variable -
and tests can override it through FastAPI's dependency overrides.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_SMTP_PORT = 587
DEFAULT_CONTACT_RECIPIENT = "office@equicrew.com"


@dataclass(frozen=True)
class Settings:
    """Configuration of the api service.

    SMTP_* values are external: without them the product still starts and the
    contact endpoint answers 503.
    """

    smtp_host: str | None = None
    smtp_port: int = DEFAULT_SMTP_PORT
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    contact_recipient: str = DEFAULT_CONTACT_RECIPIENT
    frontend_origin: str | None = None

    @property
    def smtp_configured(self) -> bool:
        """True only when host, a valid port and the sender address are set."""
        return bool(self.smtp_host) and 0 < self.smtp_port <= 65535 and bool(self.smtp_from)

    def __repr__(self) -> str:
        # Never let the password reach a log line or a traceback.
        return (
            f"Settings(smtp_host_set={bool(self.smtp_host)}, smtp_port={self.smtp_port}, "
            f"smtp_user_set={bool(self.smtp_user)}, "
            f"smtp_password_set={bool(self.smtp_password)}, "
            f"smtp_from_set={bool(self.smtp_from)}, "
            f"contact_recipient={self.contact_recipient!r}, "
            f"frontend_origin={self.frontend_origin!r})"
        )


def _env(name: str) -> str | None:
    """The stripped value of an environment variable; empty counts as unset."""
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _port(name: str, default: int) -> int:
    """Parse a port variable; an unusable value disables SMTP instead of crashing."""
    raw = _env(name)
    if raw is None:
        return default
    try:
        port = int(raw)
    except ValueError:
        logger.warning("%s is not a number - SMTP stays disabled", name)
        return 0
    if not 0 < port <= 65535:
        logger.warning("%s is out of range - SMTP stays disabled", name)
        return 0
    return port


def get_settings() -> Settings:
    """Read the settings from the environment (FastAPI dependency, overridable in tests)."""
    return Settings(
        smtp_host=_env("SMTP_HOST"),
        smtp_port=_port("SMTP_PORT", DEFAULT_SMTP_PORT),
        smtp_user=_env("SMTP_USER"),
        smtp_password=os.environ.get("SMTP_PASSWORD") or None,
        smtp_from=_env("SMTP_FROM"),
        contact_recipient=_env("CONTACT_RECIPIENT") or DEFAULT_CONTACT_RECIPIENT,
        frontend_origin=_env("FRONTEND_ORIGIN"),
    )
