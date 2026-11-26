"""Local-only transport probe for JOB-005 recovery notification.

This deliberately accepts no real order, recipient or recovery token.
The relay must expose only the sandbox webhook over a private Unix socket.
"""
import http.client
import json
import re
import socket

SANDBOX_PATH = "/webhook/zunpy-job005-recovery-sandbox"


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 35):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
        except BaseException:
            sock.close()
            raise
        self.sock = sock


def probe_sandbox(socket_path: str, secret: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", secret):
        raise ValueError("Invalid sandbox credential format.")
    body = json.dumps({
        "sandbox": True,
        "recipient": "buyer@example.com",
        "order_id": "ZJ-RECOVERY-TEST",
    }).encode()
    conn = UnixHTTPConnection(socket_path)
    try:
        conn.request("POST", SANDBOX_PATH, body=body, headers={
            "Content-Type": "application/json",
            "X-ZUNPY-Recovery-Auth": secret,
        })
        with conn.getresponse() as response:
            if response.status != 200:
                raise RuntimeError(f"Sandbox relay returned HTTP {response.status}.")
    finally:
        conn.close()
