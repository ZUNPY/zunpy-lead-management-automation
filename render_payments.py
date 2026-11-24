from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import Settings


class PaymentConfigurationError(RuntimeError):
    pass


class PaymentProviderError(RuntimeError):
    pass


class PaymentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CreatedPayPalOrder:
    order_id: str
    approval_url: str | None
    claim_secret: str


@dataclass(frozen=True)
class VerifiedPayPalOrder:
    order_id: str
    capture_id: str
    payer_email: str
    amount_cents: int
    currency: str
    claim_secret: str


_ALLOWED_BASE_URLS = {
    "https://api-m.sandbox.paypal.com",
    "https://api-m.paypal.com",
}


def _api_base_url() -> str:
    value = os.getenv(
        "PAYPAL_API_BASE_URL",
        "https://api-m.sandbox.paypal.com",
    ).rstrip("/")
    if value not in _ALLOWED_BASE_URLS:
        raise PaymentConfigurationError(
            "PAYPAL_API_BASE_URL must be an official PayPal API endpoint."
        )
    return value


def _credentials(settings: Settings) -> tuple[str, str]:
    if not settings.paypal_client_id or settings.paypal_client_secret is None:
        raise PaymentConfigurationError(
            "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are required."
        )
    return settings.paypal_client_id, settings.paypal_client_secret.get_secret_value()


def _request_json(
    *,
    url: str,
    method: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raise PaymentProviderError(f"PayPal HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise PaymentProviderError(f"PayPal request failed: {type(exc).__name__}") from exc

    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentProviderError("PayPal returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise PaymentProviderError("PayPal returned an unexpected JSON payload.")
    return payload


def _access_token(settings: Settings) -> str:
    client_id, client_secret = _credentials(settings)
    encoded = b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    payload = _request_json(
        url=f"{_api_base_url()}/v1/oauth2/token",
        method="POST",
        headers={
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=b"grant_type=client_credentials",
    )
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise PaymentProviderError("PayPal access token missing from response.")
    return token


def _bearer_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_access_token(settings)}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _find_link(payload: dict[str, Any], rel: str) -> str | None:
    links = payload.get("links")
    if not isinstance(links, list):
        return None
    for item in links:
        if isinstance(item, dict) and item.get("rel") == rel:
            href = item.get("href")
            if isinstance(href, str) and href:
                return href
    return None


def create_paypal_order(
    settings: Settings,
    *,
    amount_cents: int,
    currency: str,
    claim_secret: str,
) -> CreatedPayPalOrder:
    if amount_cents <= 0:
        raise PaymentValidationError("Amount must be positive.")
    normalized_currency = currency.upper()
    value = f"{Decimal(amount_cents) / Decimal(100):.2f}"
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "ZUNPY-JOB001",
                "custom_id": f"ZUNPY:{claim_secret}",
                "description": "ZUNPY invoice PDF to structured CSV",
                "amount": {
                    "currency_code": normalized_currency,
                    "value": value,
                },
            }
        ],
    }
    headers = _bearer_headers(settings)
    headers["PayPal-Request-Id"] = f"ZUNPY-CREATE-{claim_secret}"[:108]
    headers["Prefer"] = "return=representation"
    payload = _request_json(
        url=f"{_api_base_url()}/v2/checkout/orders",
        method="POST",
        headers=headers,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
    )
    order_id = payload.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise PaymentProviderError("PayPal order id missing from create response.")
    return CreatedPayPalOrder(
        order_id=order_id,
        approval_url=_find_link(payload, "payer-action") or _find_link(payload, "approve"),
        claim_secret=claim_secret,
    )


def _amount_to_cents(value: object) -> int:
    if not isinstance(value, str):
        raise PaymentValidationError("PayPal amount is missing.")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise PaymentValidationError("PayPal amount is invalid.") from exc
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise PaymentValidationError("PayPal amount has unsupported precision.")
    return int(cents)


def _verify_completed_payload(
    payload: dict[str, Any],
    *,
    expected_claim_secret: str,
) -> VerifiedPayPalOrder:
    order_id = payload.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise PaymentValidationError("PayPal order id is missing.")
    if payload.get("status") != "COMPLETED":
        raise PaymentValidationError("PayPal order is not completed.")

    purchase_units = payload.get("purchase_units")
    if not isinstance(purchase_units, list) or len(purchase_units) != 1:
        raise PaymentValidationError("Expected exactly one PayPal purchase unit.")
    purchase_unit = purchase_units[0]
    if not isinstance(purchase_unit, dict):
        raise PaymentValidationError("PayPal purchase unit is invalid.")

    custom_id = purchase_unit.get("custom_id")
    expected_custom_id = f"ZUNPY:{expected_claim_secret}"
    if custom_id != expected_custom_id:
        raise PaymentValidationError("PayPal claim secret does not match.")

    payments = purchase_unit.get("payments")
    captures = payments.get("captures") if isinstance(payments, dict) else None
    completed = [
        capture
        for capture in (captures if isinstance(captures, list) else [])
        if isinstance(capture, dict) and capture.get("status") == "COMPLETED"
    ]
    if len(completed) != 1:
        raise PaymentValidationError("Expected exactly one completed PayPal capture.")
    capture = completed[0]

    capture_id = capture.get("id")
    amount = capture.get("amount")
    if not isinstance(capture_id, str) or not capture_id:
        raise PaymentValidationError("PayPal capture id is missing.")
    if not isinstance(amount, dict):
        raise PaymentValidationError("PayPal capture amount is missing.")
    currency = amount.get("currency_code")
    if not isinstance(currency, str) or len(currency) != 3:
        raise PaymentValidationError("PayPal capture currency is invalid.")
    amount_cents = _amount_to_cents(amount.get("value"))

    payer = payload.get("payer")
    payer_email = payer.get("email_address") if isinstance(payer, dict) else None
    if not payer_email:
        payment_source = payload.get("payment_source")
        paypal_source = (
            payment_source.get("paypal") if isinstance(payment_source, dict) else None
        )
        payer_email = (
            paypal_source.get("email_address")
            if isinstance(paypal_source, dict)
            else None
        )
    if not isinstance(payer_email, str) or "@" not in payer_email:
        raise PaymentValidationError("PayPal payer email is missing.")

    return VerifiedPayPalOrder(
        order_id=order_id,
        capture_id=capture_id,
        payer_email=payer_email,
        amount_cents=amount_cents,
        currency=currency.upper(),
        claim_secret=expected_claim_secret,
    )


def show_paypal_order(
    settings: Settings,
    *,
    paypal_order_id: str,
    claim_secret: str,
) -> VerifiedPayPalOrder:
    payload = _request_json(
        url=f"{_api_base_url()}/v2/checkout/orders/{quote(paypal_order_id, safe='')}",
        method="GET",
        headers=_bearer_headers(settings),
    )
    return _verify_completed_payload(payload, expected_claim_secret=claim_secret)


def capture_paypal_order(
    settings: Settings,
    *,
    paypal_order_id: str,
    claim_secret: str,
) -> VerifiedPayPalOrder:
    try:
        headers = _bearer_headers(settings)
        headers["PayPal-Request-Id"] = f"ZUNPY-CAPTURE-{paypal_order_id}"[:108]
        headers["Prefer"] = "return=representation"
        payload = _request_json(
            url=f"{_api_base_url()}/v2/checkout/orders/{quote(paypal_order_id, safe='')}/capture",
            method="POST",
            headers=headers,
            data=b"{}",
        )
        return _verify_completed_payload(payload, expected_claim_secret=claim_secret)
    except (PaymentProviderError, PaymentValidationError):
        # A retry may arrive after PayPal has already captured the order, and
        # some capture responses can be minimal. Show Order Details is the
        # authoritative recovery path in both cases.
        return show_paypal_order(
            settings,
            paypal_order_id=paypal_order_id,
            claim_secret=claim_secret,
        )


def verify_webhook_signature(
    settings: Settings,
    *,
    headers: dict[str, str],
    event: dict[str, Any],
) -> bool:
    if not settings.paypal_webhook_id:
        raise PaymentConfigurationError("PAYPAL_WEBHOOK_ID is required.")

    required = {
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "cert_url": headers.get("paypal-cert-url"),
        "auth_algo": headers.get("paypal-auth-algo"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
    }
    if any(not isinstance(value, str) or not value for value in required.values()):
        raise PaymentValidationError("Required PayPal webhook headers are missing.")

    body = {
        **required,
        "webhook_id": settings.paypal_webhook_id,
        "webhook_event": event,
    }
    payload = _request_json(
        url=f"{_api_base_url()}/v1/notifications/verify-webhook-signature",
        method="POST",
        headers=_bearer_headers(settings),
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
    )
    return payload.get("verification_status") == "SUCCESS"
