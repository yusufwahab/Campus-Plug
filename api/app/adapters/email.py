"""Email adapter. LocalEmail is a clearly labelled TEST implementation: it sends nothing."""

import logging
from typing import Protocol

logger = logging.getLogger("campusplug.email")


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class LocalEmail:
    """TEST ADAPTER. Keeps messages in memory; never contacts a real mailbox."""

    outbox: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))
        logger.info("local-email queued (not sent)")


def get_email() -> EmailSender:
    # A real SMTP/Resend adapter is selected here once the owner supplies credentials (docs/OWNER_ACTIONS.md).
    return LocalEmail()
