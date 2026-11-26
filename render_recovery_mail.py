"""Candidate production delivery contract. NOT wired into the public API.

Requires a separate authenticated relay route and a mail workflow that returns
an explicit acknowledgement only after Gmail accepts the send. Never retry an
ambiguous send automatically. No raw credential or recipient in diagnostics.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from render_recovery_bridge import UnixHTTPConnection

PRODUCTION_PATH = "/webhook/zunpy-job005-recovery-mail"
ACK = {"status": "accepted"}
ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"


class RecoveryMailError(RuntimeError):
    """Delivery could not be confirmed; details intentionally redacted."""


def valid_recipient(value: str) -> bool:
    # Deliberately support a single ASCII dot-atom mailbox only.
    # No display names, commas, whitespace, line breaks or quoted local parts.
    if not isinstance(value, str) or len(value) > 254 or value.count("@") != 1:
        return False
    local, domain = value.split("@")
    return bool(len(local) <= 64
                and re.fullmatch(ATOM + r"(?:\." + ATOM + r")*", local)
                and re.fullmatch(LABEL + r"(?:\." + LABEL + r")+", domain))


def deliver_recovery_mail(delivery, *, socket_path: str, secret: str,
                          now: datetime | None = None) -> None:
    if not re.fullmatch(r"ZJ-[A-F0-9]{16}", delivery.order_id):
        raise ValueError("Invalid order identifier.")
    if not valid_recipient(delivery.recipient):
        raise ValueError("Unsupported recipient mailbox.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", delivery.raw_token):
        raise ValueError("Invalid recovery credential format.")
    if not re.fullmatch(r"[0-9a-f]{64}", secret):
        raise ValueError("Invalid mail authentication format.")
    if not PurePosixPath(socket_path).is_absolute():
        raise ValueError("Absolute private socket path required.")
    current = now or datetime.now(timezone.utc)
    expiry = delivery.expires_at
    if (current.utcoffset() is None or expiry.utcoffset() is None
            or not current < expiry <= current + timedelta(minutes=15)):
        raise ValueError("Invalid recovery expiry.")
    body = json.dumps({
        "order_id": delivery.order_id,
        "recipient": delivery.recipient,
        "recovery_token": delivery.raw_token,
        "expires_at": expiry.astimezone(timezone.utc).isoformat(),
    }).encode()
    try:
        conn = UnixHTTPConnection(socket_path, timeout=35)
        try:
            conn.request("POST", PRODUCTION_PATH, body=body, headers={
                "Content-Type": "application/json",
                "X-ZUNPY-Recovery-Auth": secret,
            })
            with conn.getresponse() as response:
                if response.status != 200:
                    raise RecoveryMailError("Recovery mail delivery unconfirmed.")
                raw = response.read(257)
                if len(raw) > 256 or json.loads(raw) != ACK:
                    raise RecoveryMailError("Recovery mail delivery unconfirmed.")
        finally:
            conn.close()
    except Exception:
        raise RecoveryMailError("Recovery mail delivery unconfirmed.") from None
