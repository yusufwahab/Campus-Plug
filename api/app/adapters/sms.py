"""SMS / WhatsApp adapter. LocalSms is a clearly labelled TEST implementation: it sends nothing."""

import logging
from typing import Protocol

logger = logging.getLogger("campusplug.sms")


class SmsSender(Protocol):
    def send(self, phone: str, message: str) -> None: ...


class LocalSms:
    """TEST ADAPTER. Keeps messages in memory so tests and local runs can read them; never contacts a real phone."""

    outbox: list[tuple[str, str]] = []

    def send(self, phone: str, message: str) -> None:
        self.outbox.append((phone, message))
        logger.info("local-sms queued (not sent)")


def get_sms() -> SmsSender:
    # A real provider adapter is selected here once the owner supplies credentials (docs/OWNER_ACTIONS.md).
    return LocalSms()
