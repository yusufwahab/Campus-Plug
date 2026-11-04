"""Payment provider adapter.

LocalProvider is a clearly labelled TEST implementation: no real money moves and checkout is a local simulation page.
PaystackProvider talks to Paystack in TEST mode first (use sk_test_ keys). It has not been exercised against Paystack's
servers in this repository: automated tests use a mocked HTTP transport (see docs/OWNER_ACTIONS.md).
"""

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class InitResult:
    checkout_url: str
    provider_reference: str


@dataclass(frozen=True)
class VerifyResult:
    status: str  # success | failed | pending
    amount_kobo: int
    fee_kobo: int
    currency: str
    reference: str


@dataclass(frozen=True)
class WebhookEvent:
    key: str  # unique per delivery of the same event, used for idempotency
    type: str  # e.g. charge.success
    reference: str


@dataclass(frozen=True)
class MoneyResult:
    status: str  # success | pending | failed
    provider_ref: str


@dataclass(frozen=True)
class Recipient:
    bank_name: str
    account_number: str
    account_name: str


class PaymentProvider(Protocol):
    name: str

    def initialize(self, *, reference: str, amount_kobo: int, email: str, callback_url: str) -> InitResult: ...
    def verify(self, reference: str) -> VerifyResult: ...
    def verify_signature(self, raw_body: bytes, signature: str | None) -> bool: ...
    def parse_event(self, raw_body: bytes) -> WebhookEvent | None: ...
    def refund(self, *, reference: str, amount_kobo: int) -> MoneyResult: ...
    def transfer(self, *, recipient: Recipient, amount_kobo: int, reference: str) -> MoneyResult: ...


# ---- local test provider ------------------------------------------------------------------------------------------


class LocalProvider:
    """TEST ADAPTER. Transactions live in memory; checkout is the local page /checkout/local. Never moves real money."""

    name = "local"
    transactions: dict[str, dict[str, Any]] = {}

    def _secret(self) -> bytes:
        return get_settings().jwt_secret.encode()

    def initialize(self, *, reference: str, amount_kobo: int, email: str, callback_url: str) -> InitResult:
        self.transactions[reference] = {"amount": amount_kobo, "status": "pending", "fee": min(amount_kobo * 15 // 1000 + 10_000, 200_000)}
        return InitResult(checkout_url=f"/checkout/local?reference={reference}", provider_reference=reference)

    def verify(self, reference: str) -> VerifyResult:
        tx = self.transactions.get(reference)
        if tx is None:
            return VerifyResult("failed", 0, 0, "NGN", reference)
        return VerifyResult(tx["status"], tx["amount"], tx["fee"], "NGN", reference)

    def complete(self, reference: str, success: bool) -> bytes:
        """Simulates the customer finishing checkout. Returns the signed webhook body the provider would post."""
        tx = self.transactions.get(reference)
        if tx is None:
            raise KeyError(reference)
        tx["status"] = "success" if success else "failed"
        return json.dumps(
            {"event": "charge.success" if success else "charge.failed", "data": {"reference": reference, "id": secrets.token_hex(6)}}
        ).encode()

    def sign(self, raw_body: bytes) -> str:
        return hmac.new(self._secret(), raw_body, hashlib.sha512).hexdigest()

    def verify_signature(self, raw_body: bytes, signature: str | None) -> bool:
        return bool(signature) and hmac.compare_digest(self.sign(raw_body), signature or "")

    def parse_event(self, raw_body: bytes) -> WebhookEvent | None:
        data = json.loads(raw_body)
        ref = data.get("data", {}).get("reference")
        return (
            WebhookEvent(key=f"{data.get('event')}:{data.get('data', {}).get('id') or ref}", type=data.get("event", ""), reference=ref)
            if ref
            else None
        )

    def refund(self, *, reference: str, amount_kobo: int) -> MoneyResult:
        return MoneyResult("success", f"local-refund-{reference}-{amount_kobo}")

    def transfer(self, *, recipient: Recipient, amount_kobo: int, reference: str) -> MoneyResult:
        return MoneyResult("success", f"local-transfer-{reference}")


# ---- Paystack ----------------------------------------------------------------------------------------------------


class PaystackProvider:
    """Paystack REST API. Signature: HMAC-SHA512 of the raw body with the secret key, in the x-paystack-signature header."""

    name = "paystack"

    def __init__(self, secret_key: str, client: httpx.Client | None = None) -> None:
        self.secret_key = secret_key
        self.http = client or httpx.Client(base_url="https://api.paystack.co", timeout=15)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}"}

    def _call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        res = self.http.request(method, path, headers=self._headers(), **kwargs)
        body = res.json()
        if res.status_code >= 400 or not body.get("status"):
            raise RuntimeError(f"Paystack {path} failed with {res.status_code}")
        return body["data"]

    def initialize(self, *, reference: str, amount_kobo: int, email: str, callback_url: str) -> InitResult:
        data = self._call(
            "POST",
            "/transaction/initialize",
            json={"reference": reference, "amount": amount_kobo, "email": email, "currency": "NGN", "callback_url": callback_url},
        )
        return InitResult(checkout_url=data["authorization_url"], provider_reference=data["reference"])

    def verify(self, reference: str) -> VerifyResult:
        data = self._call("GET", f"/transaction/verify/{reference}")
        status = {"success": "success", "failed": "failed", "abandoned": "failed"}.get(data["status"], "pending")
        return VerifyResult(status, int(data["amount"]), int(data.get("fees") or 0), data.get("currency", "NGN"), data["reference"])

    def verify_signature(self, raw_body: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        expected = hmac.new(self.secret_key.encode(), raw_body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_event(self, raw_body: bytes) -> WebhookEvent | None:
        payload = json.loads(raw_body)
        data = payload.get("data") or {}
        ref = data.get("reference")
        return (
            WebhookEvent(key=f"{payload.get('event')}:{data.get('id') or ref}", type=payload.get("event", ""), reference=ref)
            if ref
            else None
        )

    def refund(self, *, reference: str, amount_kobo: int) -> MoneyResult:
        data = self._call("POST", "/refund", json={"transaction": reference, "amount": amount_kobo})
        return MoneyResult("success" if data.get("status") in ("processed", "success") else "pending", str(data.get("id", "")))

    def transfer(self, *, recipient: Recipient, amount_kobo: int, reference: str) -> MoneyResult:
        from app.banks import bank_code

        code = bank_code(recipient.bank_name)
        if code is None:
            raise ValueError("Unknown bank")
        rec = self._call(
            "POST",
            "/transferrecipient",
            json={
                "type": "nuban",
                "name": recipient.account_name,
                "account_number": recipient.account_number,
                "bank_code": code,
                "currency": "NGN",
            },
        )
        data = self._call(
            "POST",
            "/transfer",
            json={
                "source": "balance",
                "amount": amount_kobo,
                "recipient": rec["recipient_code"],
                "reference": reference,
                "reason": "Campus Plug payout",
            },
        )
        return MoneyResult("success" if data.get("status") == "success" else "pending", str(data.get("transfer_code", "")))


_local = LocalProvider()


def get_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.payment_provider == "paystack":
        if settings.is_production and not settings.paystack_secret_key.startswith("sk_"):
            raise RuntimeError("PAYSTACK_SECRET_KEY is required")
        return PaystackProvider(settings.paystack_secret_key)
    return _local
