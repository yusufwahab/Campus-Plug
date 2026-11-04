"""Email adapter. LocalEmail is a clearly labelled TEST implementation: it sends nothing."""

import logging
from typing import Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger("campusplug.email")


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class LocalEmail:
    """TEST ADAPTER. Keeps messages in memory; never contacts a real mailbox."""

    outbox: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))
        logger.info("local-email queued (not sent)")


class BrevoEmail:
    """Real email through Brevo's transactional API (https://developers.brevo.com). Needs BREVO_API_KEY and a verified sender.

    Mock-tested only: it has never sent a real message (docs/OWNER_ACTIONS.md).
    """

    URL = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, api_key: str, sender_email: str, sender_name: str) -> None:
        self.api_key, self.sender_email, self.sender_name = api_key, sender_email, sender_name

    def send(self, to: str, subject: str, body: str) -> None:
        payload = {
            "sender": {"email": self.sender_email, "name": self.sender_name},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": body,
        }
        try:
            res = httpx.post(self.URL, json=payload, headers={"api-key": self.api_key, "accept": "application/json"}, timeout=10.0)
        except httpx.HTTPError:
            logger.error("brevo email failed: network error")
            return
        if res.status_code >= 300:
            # Never log the recipient or body (they can contain reset links); status and Brevo's error code are enough.
            logger.error("brevo email failed: status=%s code=%s", res.status_code, _code(res))


def _code(res: httpx.Response) -> str:
    try:
        return str(res.json().get("code", ""))
    except ValueError:
        return ""


def get_email() -> EmailSender:
    s = get_settings()
    if s.email_provider == "brevo" and s.brevo_api_key and s.email_from:
        return BrevoEmail(s.brevo_api_key, s.email_from, s.email_from_name)
    return LocalEmail()
