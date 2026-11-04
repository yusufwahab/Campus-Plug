"""Paystack adapter against a mocked HTTP transport. These tests prove request shapes and signature handling;
they do NOT prove behaviour against Paystack's live servers (see docs/OWNER_ACTIONS.md)."""

import hashlib
import hmac
import json

import httpx
import pytest

from app.adapters.payments import PaystackProvider, Recipient

SECRET = "sk_test_dummy_key_for_unit_tests"


def make(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.paystack.co")
    return PaystackProvider(SECRET, client)


def ok(data):
    return httpx.Response(200, json={"status": True, "message": "ok", "data": data})


def test_signature_is_hmac_sha512_of_the_raw_body():
    provider = make(lambda r: ok({}))
    body = json.dumps({"event": "charge.success", "data": {"reference": "R1", "id": 9}}).encode()
    good = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    assert provider.verify_signature(body, good)
    assert not provider.verify_signature(body, good[:-1] + ("0" if good[-1] != "0" else "1"))
    assert not provider.verify_signature(body + b" ", good)  # any change to the body breaks it
    assert not provider.verify_signature(body, None) and not provider.verify_signature(body, "")
    other = hmac.new(b"another-secret", body, hashlib.sha512).hexdigest()
    assert not provider.verify_signature(body, other)


def test_initialize_sends_amount_in_kobo_and_a_reference():
    seen = {}

    def handler(request):
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return ok({"authorization_url": "https://checkout.paystack.com/abc", "reference": "CPO-1"})

    result = make(handler).initialize(
        reference="CPO-1", amount_kobo=1_050_000, email="b@example.com", callback_url="https://site/checkout/CP-O-1/result"
    )
    assert seen["url"].endswith("/transaction/initialize") and seen["auth"] == f"Bearer {SECRET}"
    assert seen["body"] == {
        "reference": "CPO-1",
        "amount": 1_050_000,
        "email": "b@example.com",
        "currency": "NGN",
        "callback_url": "https://site/checkout/CP-O-1/result",
    }
    assert (result.checkout_url, result.provider_reference) == ("https://checkout.paystack.com/abc", "CPO-1")


def test_verify_maps_statuses_and_reads_amount_currency_and_fees():
    def handler(request):
        assert request.url.path.endswith("/transaction/verify/CPO-1")
        return ok({"status": "success", "amount": 500_000, "fees": 12_500, "currency": "NGN", "reference": "CPO-1"})

    v = make(handler).verify("CPO-1")
    assert (v.status, v.amount_kobo, v.fee_kobo, v.currency) == ("success", 500_000, 12_500, "NGN")
    assert make(lambda r: ok({"status": "abandoned", "amount": 1, "currency": "NGN", "reference": "x"})).verify("x").status == "failed"
    assert make(lambda r: ok({"status": "ongoing", "amount": 1, "currency": "NGN", "reference": "x"})).verify("x").status == "pending"


def test_provider_errors_raise_instead_of_pretending_success():
    provider = make(lambda r: httpx.Response(400, json={"status": False, "message": "Invalid key"}))
    with pytest.raises(RuntimeError):
        provider.verify("CPO-1")
    with pytest.raises(RuntimeError):
        make(lambda r: httpx.Response(200, json={"status": False, "message": "nope"})).verify("CPO-1")


def test_parse_event_builds_an_idempotency_key_from_event_and_transaction_id():
    provider = make(lambda r: ok({}))
    raw = json.dumps({"event": "charge.success", "data": {"reference": "CPO-7", "id": 123456}}).encode()
    event = provider.parse_event(raw)
    assert (event.type, event.reference, event.key) == ("charge.success", "CPO-7", "charge.success:123456")
    assert provider.parse_event(json.dumps({"event": "ping", "data": {}}).encode()) is None


def test_refund_posts_transaction_and_amount():
    seen = {}

    def handler(request):
        seen["path"], seen["body"] = request.url.path, json.loads(request.content)
        return ok({"id": 55, "status": "processed"})

    result = make(handler).refund(reference="CPO-1", amount_kobo=250_000)
    assert seen["path"].endswith("/refund") and seen["body"] == {"transaction": "CPO-1", "amount": 250_000}
    assert result.status == "success" and result.provider_ref == "55"


def test_transfer_creates_a_recipient_with_the_bank_code_then_transfers_kobo():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if request.url.path.endswith("/transferrecipient"):
            return ok({"recipient_code": "RCP_1"})
        return ok({"status": "success", "transfer_code": "TRF_9"})

    result = make(handler).transfer(recipient=Recipient("GTBank", "0123456789", "Kemi A"), amount_kobo=800_000, reference="CP-O-1-payout-1")
    assert (
        calls[0][0].endswith("/transferrecipient") and calls[0][1]["bank_code"] == "058" and calls[0][1]["account_number"] == "0123456789"
    )
    assert calls[1][0].endswith("/transfer") and calls[1][1]["amount"] == 800_000 and calls[1][1]["recipient"] == "RCP_1"
    assert calls[1][1]["reference"] == "CP-O-1-payout-1"
    assert (result.status, result.provider_ref) == ("success", "TRF_9")


def test_transfer_to_an_unknown_bank_fails_before_calling_paystack():
    called = []
    provider = make(lambda r: called.append(r) or ok({}))
    with pytest.raises(ValueError):
        provider.transfer(recipient=Recipient("Imaginary Bank", "0123456789", "X"), amount_kobo=100, reference="r")
    assert called == []
