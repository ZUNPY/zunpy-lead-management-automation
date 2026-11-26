"""Synthetic delivery adapter for the private n8n recovery relay.

Only fictional Sandbox orders are accepted. Production delivery and public
activation remain separate approval gates. No real secrets are logged.
"""
import json
import re
from datetime import timezone
from render_recovery_bridge import UnixHTTPConnection, SANDBOX_PATH


def deliver_sandbox_recovery(delivery, *, socket_path: str, secret: str) -> None:
    if delivery.order_id != "ZJ-RECOVERY-TEST" or delivery.recipient != "buyer@example.com":
        raise ValueError("Only synthetic recovery fixtures are allowed.")
    if not re.fullmatch(r"[0-9a-f]{64}", secret):
        raise ValueError("Invalid sandbox authentication format.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", delivery.raw_token):
        raise ValueError("Invalid recovery token format.")
    if delivery.expires_at.tzinfo is None:
        raise ValueError("Timezone-aware expiry required.")
    body = json.dumps({
        "sandbox": True,
        "order_id": delivery.order_id,
        "recipient": delivery.recipient,
        "recovery_token": delivery.raw_token,
        "expires_at": delivery.expires_at.astimezone(timezone.utc).isoformat(),
    }).encode()
    conn = UnixHTTPConnection(socket_path)
    try:
        conn.request("POST", SANDBOX_PATH, body=body, headers={
            "Content-Type": "application/json",
            "X-ZUNPY-Recovery-Auth": secret,
        })
        with conn.getresponse() as response:
            if response.status != 200:
                raise RuntimeError(f"Sandbox delivery returned HTTP {response.status}.")
    finally:
        conn.close()
