"""Web push adapter. LocalPush is the TEST implementation (sends nothing). WebPush needs VAPID keys from the owner."""

import json
import logging
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger("campusplug.push")


class PushSender(Protocol):
    def send(self, endpoint: str, p256dh: str, auth: str, title: str, body: str, url: str) -> bool:
        """Returns False when the subscription is gone and should be deleted."""


class LocalPush:
    """TEST ADAPTER: records pushes in memory instead of contacting a push service."""

    outbox: list[dict[str, str]] = []

    def send(self, endpoint: str, p256dh: str, auth: str, title: str, body: str, url: str) -> bool:
        self.outbox.append({"endpoint": endpoint, "title": title, "body": body, "url": url})
        return True


class WebPush:
    """Real web push through pywebpush. Not exercised by automated tests (needs VAPID keys and a live browser)."""

    def send(self, endpoint: str, p256dh: str, auth: str, title: str, body: str, url: str) -> bool:
        from pywebpush import WebPushException, webpush

        settings = get_settings()
        try:
            webpush(
                subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
            return True
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                return False
            logger.warning("web push failed with status %s", status)
            return True


def get_push() -> PushSender:
    return WebPush() if get_settings().vapid_private_key else LocalPush()
