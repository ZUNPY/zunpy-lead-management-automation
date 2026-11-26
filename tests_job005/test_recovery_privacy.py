"""Verify redaction and explicit no-trust proxy policy without external services."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from pydantic import SecretStr
from uvicorn import Config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import get_settings
from app.db.session import get_db
import render_public_recovery as public
from render_recovery_routes import router as private_router
from render_paypal import router as payment_router


class RecoveryPrivacyTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(public.router, prefix="/v1")
        app.include_router(private_router, prefix="/v1")
        app.include_router(payment_router, prefix="/v1")
        self.db = Mock()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            internal_service_token=SecretStr("synthetic-internal-secret"))
        self.app = app
        # Match the explicit candidate startup policy; do not trust any
        # X-Forwarded-For even when the transport peer is loopback.
        startup = (ROOT / "render_start.sh").read_text()
        self.assertIn("--no-proxy-headers", startup.splitlines()[-1])
        cfg = Config(app, proxy_headers=False, log_config=None, lifespan="off")
        cfg.load()
        self.asgi = cfg.loaded_app

    def request(self, path, payload, peer="127.0.0.1", forwarded="203.0.113.1"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        scope = {
            "type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1",
            "method":"POST","scheme":"http","path":path,"raw_path":path.encode(),
            "query_string":b"","root_path":"",
            "headers":[(b"content-type", b"application/json"),
                       (b"authorization", b"Bearer synthetic-internal-secret"),
                       (b"x-forwarded-for", forwarded.encode()),
                       (b"cf-connecting-ip", forwarded.encode())],
            "client":(peer,12345),"server":("localhost",80),
        }
        messages = []
        async def receive():
            return {"type":"http.request","body":body,"more_body":False}
        async def send(message):
            messages.append(message)
        asyncio.run(self.asgi(scope, receive, send))
        start = next(m for m in messages if m["type"]=="http.response.start")
        raw = b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
        return start["status"], dict(start["headers"]), json.loads(raw)

    def test_validation_does_not_reflect_credentials(self):
        marker = "private-marker"
        cases = [
            ("/v1/recovery/redeem", {"order_id":"ZJ-TEST","recovery_token":marker}),
            ("/v1/internal/recovery/redeem", {"order_id":"ZJ-TEST","recovery_token":marker}),
            ("/v1/recovery/request", {"order_id":"ZJ-TEST","email":[marker]}),
            ("/v1/payments/paypal/order/TEST/capture", {"claim_secret":marker}),
            ("/v1/recovery/redeem", b'{"recovery_token":"private-marker"'),
        ]
        for path, payload in cases:
            with self.subTest(path=path):
                code, headers, body = self.request(path, payload)
                self.assertEqual(code, 422)
                self.assertEqual(headers[b"cache-control"], b"no-store")
                self.assertEqual(body, {"detail":"Invalid request."})
        self.db.execute.assert_not_called()

    def test_forwarded_headers_cannot_rotate_quota_identity(self):
        config = public.PublicRecoveryConfig(b"x"*32, Mock())
        self.app.dependency_overrides[public.get_public_recovery_config] = lambda: config
        payload = {"order_id":"ZJ-TEST","email":"buyer@example.com"}
        with patch.object(public, "allow_request", return_value=False) as quota:
            for peer, spoof in [
                ("127.0.0.1","203.0.113.1"),
                ("127.0.0.1","198.51.100.2"),
                ("::ffff:127.0.0.1","192.0.2.3"),
                ("192.0.2.42","203.0.113.1"),
                ("2001:db8:1::1","203.0.113.1"),
                ("2001:db8:1::abcd","198.51.100.2"),
            ]:
                code, _, body = self.request("/v1/recovery/request", payload, peer, spoof)
                self.assertEqual((code,body),(202,{"status":"accepted"}))
            keys = [c.kwargs["source_key"] for c in quota.call_args_list]
            self.assertEqual(len(keys),6)
            self.assertEqual(keys[0],keys[1])
            self.assertEqual(keys[0],keys[2])
            self.assertNotEqual(keys[0],keys[3])
            self.assertEqual(keys[4],keys[5])
            self.assertNotEqual(keys[3],keys[4])
        config.deliver.assert_not_called()

    def test_recovery_still_fails_closed(self):
        code, headers, body = self.request("/v1/recovery/request",
            {"order_id":"ZJ-TEST","email":"buyer@example.com"})
        self.assertEqual(code,503)
        self.assertEqual(headers[b"cache-control"],b"no-store")
        self.assertEqual(body,{"detail":"Recovery unavailable."})
        self.db.execute.assert_not_called()
