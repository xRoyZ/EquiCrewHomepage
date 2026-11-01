"""Tests for POST /api/contact and the SMTP mailer (smtplib is mocked)."""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Iterator
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

SMTP_HOST = "smtp.secret-host.example.test"
SMTP_USER = "mailer-account-user"
SMTP_PASSWORD = "very-secret-smtp-password"
SMTP_FROM = "website@equicrew.example.test"
RECIPIENT = "office@equicrew.com"

VALID = {
    "first_name": "Anna",
    "last_name": "Muster",
    "email": "anna.muster@example.org",
    "message": "Hallo EquiCrew,\nich interessiere mich für den EquiCube.",
}


def smtp_settings(port: int = 587) -> Settings:
    return Settings(
        smtp_host=SMTP_HOST,
        smtp_port=port,
        smtp_user=SMTP_USER,
        smtp_password=SMTP_PASSWORD,
        smtp_from=SMTP_FROM,
        contact_recipient=RECIPIENT,
        frontend_origin=None,
    )


@pytest.fixture
def smtp_mock() -> Iterator[MagicMock]:
    """smtplib.SMTP replaced by a mock; also SMTP_SSL so no real socket ever opens."""
    with (
        patch("smtplib.SMTP") as smtp_cls,
        patch("smtplib.SMTP_SSL") as smtp_ssl_cls,
    ):
        smtp_ssl_cls.side_effect = AssertionError("SMTP_SSL must not be used on port 587")
        yield smtp_cls


@pytest.fixture
def smtp_client() -> Iterator[TestClient]:
    """Client whose settings have SMTP configured."""
    app = create_app()
    app.dependency_overrides[get_settings] = smtp_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def connection(smtp_cls: MagicMock) -> MagicMock:
    """The object the mailer uses inside `with smtplib.SMTP(...) as connection`."""
    return smtp_cls.return_value.__enter__.return_value


def sent_mails(smtp_cls: MagicMock) -> list[EmailMessage]:
    return [call.args[0] for call in connection(smtp_cls).send_message.call_args_list]


# --- successful send -----------------------------------------------------------


def test_valid_submission_sends_exactly_one_mail(
    smtp_client: TestClient, smtp_mock: MagicMock
) -> None:
    response = smtp_client.post("/api/contact", json=VALID)

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    smtp_mock.assert_called_once()
    assert smtp_mock.call_args.args[:2] == (SMTP_HOST, 587)
    connection(smtp_mock).starttls.assert_called_once()
    connection(smtp_mock).login.assert_called_once_with(SMTP_USER, SMTP_PASSWORD)

    mails = sent_mails(smtp_mock)
    assert len(mails) == 1
    mail = mails[0]
    assert mail["To"] == RECIPIENT
    assert mail["From"] == SMTP_FROM
    assert mail["Reply-To"] == VALID["email"]
    assert "Anna Muster" in mail["Subject"]
    body = mail.get_content()
    assert "Anna Muster" in body
    assert VALID["email"] in body
    assert "ich interessiere mich für den EquiCube." in body


def test_fields_are_trimmed(smtp_client: TestClient, smtp_mock: MagicMock) -> None:
    payload = {
        "first_name": "  Anna ",
        "last_name": " Muster  ",
        "email": "  anna.muster@example.org ",
        "message": "  Hallo  ",
    }
    response = smtp_client.post("/api/contact", json=payload)

    assert response.status_code == 200
    mail = sent_mails(smtp_mock)[0]
    assert mail["Reply-To"] == "anna.muster@example.org"
    assert "Anna Muster" in mail["Subject"]


def test_port_465_uses_implicit_tls() -> None:
    from app.mailer import ContactData, send_contact_mail

    with patch("smtplib.SMTP_SSL") as smtp_ssl_cls, patch("smtplib.SMTP") as smtp_cls:
        send_contact_mail(
            smtp_settings(port=465),
            ContactData("Anna", "Muster", "anna.muster@example.org", "Hallo"),
        )
    smtp_cls.assert_not_called()
    smtp_ssl_cls.assert_called_once()
    conn = smtp_ssl_cls.return_value.__enter__.return_value
    conn.starttls.assert_not_called()
    conn.send_message.assert_called_once()


def test_no_login_without_credentials(smtp_mock: MagicMock) -> None:
    from app.mailer import ContactData, send_contact_mail

    settings = Settings(smtp_host=SMTP_HOST, smtp_port=25, smtp_from=SMTP_FROM)
    send_contact_mail(settings, ContactData("Anna", "Muster", "a@example.org", "Hallo"))
    connection(smtp_mock).login.assert_not_called()
    connection(smtp_mock).send_message.assert_called_once()


def test_accepted_submission_logs_no_content(
    smtp_client: TestClient, smtp_mock: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app"):
        assert smtp_client.post("/api/contact", json=VALID).status_code == 200
    logged = caplog.text
    assert "accepted" in logged
    for value in ("Anna", "Muster", VALID["email"], "EquiCube", SMTP_HOST, SMTP_PASSWORD):
        assert value not in logged


# --- validation ------------------------------------------------------------------


@pytest.mark.parametrize("field", ["first_name", "last_name", "email", "message"])
def test_missing_field_is_422(smtp_client: TestClient, smtp_mock: MagicMock, field: str) -> None:
    payload = {key: value for key, value in VALID.items() if key != field}
    response = smtp_client.post("/api/contact", json=payload)

    assert response.status_code == 422
    smtp_mock.assert_not_called()


@pytest.mark.parametrize("field", ["first_name", "last_name", "email", "message"])
def test_blank_field_is_422(smtp_client: TestClient, smtp_mock: MagicMock, field: str) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, field: "   "})

    assert response.status_code == 422
    smtp_mock.assert_not_called()


@pytest.mark.parametrize(
    "email", ["kein-at-zeichen", "anna@", "@example.org", "anna muster@example.org"]
)
def test_bad_email_is_422(smtp_client: TestClient, smtp_mock: MagicMock, email: str) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, "email": email})

    assert response.status_code == 422
    smtp_mock.assert_not_called()


@pytest.mark.parametrize(
    ("field", "length"),
    [("first_name", 101), ("last_name", 101), ("message", 5001)],
)
def test_too_long_field_is_422(
    smtp_client: TestClient, smtp_mock: MagicMock, field: str, length: int
) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, field: "a" * length})

    assert response.status_code == 422
    smtp_mock.assert_not_called()


def test_too_long_email_is_422(smtp_client: TestClient, smtp_mock: MagicMock) -> None:
    email = "a" * 60 + "@" + ".".join(["b" * 60] * 4) + ".org"
    assert len(email) > 254
    response = smtp_client.post("/api/contact", json={**VALID, "email": email})

    assert response.status_code == 422
    smtp_mock.assert_not_called()


@pytest.mark.parametrize("field", ["first_name", "last_name", "email"])
@pytest.mark.parametrize("injected", ["\r\nBcc: victim@example.org", "\nBcc: x@example.org", "\r"])
def test_line_break_in_header_field_is_422_and_sends_nothing(
    smtp_client: TestClient, smtp_mock: MagicMock, field: str, injected: str
) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, field: VALID[field] + injected})

    assert response.status_code == 422
    smtp_mock.assert_not_called()


def test_trailing_newline_in_name_is_rejected_not_trimmed(
    smtp_client: TestClient, smtp_mock: MagicMock
) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, "first_name": "Anna\n"})

    assert response.status_code == 422
    smtp_mock.assert_not_called()


def test_line_breaks_in_message_are_allowed(smtp_client: TestClient, smtp_mock: MagicMock) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, "message": "Zeile 1\r\nZeile 2"})

    assert response.status_code == 200
    assert len(sent_mails(smtp_mock)) == 1


# --- honeypot ----------------------------------------------------------------------


def test_honeypot_answers_success_and_sends_nothing(
    smtp_client: TestClient, smtp_mock: MagicMock
) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, "website": "https://spam.test"})

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    smtp_mock.assert_not_called()


def test_empty_honeypot_is_a_normal_submission(
    smtp_client: TestClient, smtp_mock: MagicMock
) -> None:
    response = smtp_client.post("/api/contact", json={**VALID, "website": ""})

    assert response.status_code == 200
    assert len(sent_mails(smtp_mock)) == 1


# --- SMTP not configured / failing ----------------------------------------------------


def test_without_smtp_config_answers_503(client: TestClient, smtp_mock: MagicMock) -> None:
    response = client.post("/api/contact", json=VALID)

    assert response.status_code == 503
    assert set(response.json()) == {"detail"}
    assert "office@equicrew.com" in response.json()["detail"]
    smtp_mock.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        smtplib.SMTPAuthenticationError(535, f"auth failed for {SMTP_USER}:{SMTP_PASSWORD}"),
        smtplib.SMTPConnectError(421, f"cannot reach {SMTP_HOST}"),
        ConnectionRefusedError(f"connection to {SMTP_HOST} refused"),
        TimeoutError(f"timed out talking to {SMTP_HOST}"),
    ],
)
def test_smtp_failure_answers_503_without_leaking(
    smtp_client: TestClient,
    smtp_mock: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    smtp_mock.side_effect = error

    with caplog.at_level(logging.DEBUG, logger="app"):
        response = smtp_client.post("/api/contact", json=VALID)

    assert response.status_code == 503
    assert set(response.json()) == {"detail"}
    body = response.text
    for secret in (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, "auth failed", "refused", "Traceback"):
        assert secret not in body
    for value in (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, "EquiCube", VALID["email"]):
        assert value not in caplog.text


def test_failure_during_send_answers_503(smtp_client: TestClient, smtp_mock: MagicMock) -> None:
    connection(smtp_mock).send_message.side_effect = smtplib.SMTPRecipientsRefused(
        {RECIPIENT: (550, b"no such user")}
    )
    response = smtp_client.post("/api/contact", json=VALID)

    assert response.status_code == 503
    assert "no such user" not in response.text
