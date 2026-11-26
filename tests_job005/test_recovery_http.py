"""HTTP contract tests without external network or an additional HTTP client."""
import asyncio
import json
from datetime import timedelta
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Order, OrderStatus
from app.security.tokens import hash_token, utcnow, verify_token
from render_recovery import recovery_tokens
from render_recovery_routes import router

ORDER = "ZJ-HTTP-TEST"
EMAIL = "buyer@example.com"
AUTH = "fictional-internal-test-secret"
OLD = "fictional-original-access"


class RecoveryHTTPTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.engine = create_engine("sqlite:///" + str(Path(temp.name) / "test.db"))
        self.addCleanup(self.engine.dispose)
        Order.__table__.create(self.engine)
        recovery_tokens.create(self.engine)
        with Session(self.engine) as db, db.begin():
            now = utcnow()
            db.add(Order(
                order_id=ORDER, customer_email=EMAIL, status=OrderStatus.WAITING_UPLOAD,
                payment_provider="paypal", payment_reference="PAYPAL:HTTPTEST",
                amount_cents=2900, currency="EUR", max_documents=1,
                access_token_hash=hash_token(OLD),
                access_expires_at=now + timedelta(days=1),
                upload_expires_at=now + timedelta(hours=1),
            ))
        self.app = FastAPI()
        self.app.include_router(router, prefix="/v1")

        def db_dependency():
            with Session(self.engine) as db:
                yield db

        self.app.dependency_overrides[get_db] = db_dependency
        self.app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            internal_service_token=SecretStr(AUTH))

    def request(self, action, payload, auth=AUTH):
        body = json.dumps(payload).encode()
        headers = [(b"content-type", b"application/json")]
        if auth is not None:
            headers.append((b"authorization", ("Bearer " + auth).encode()))
        path = "/v1/internal/recovery/" + action
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": path,
            "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": headers, "client": ("127.0.0.1", 12345),
            "server": ("localhost", 80),
        }
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(self.app(scope, receive, send))
        start = next(m for m in messages if m["type"] == "http.response.start")
        data = b"".join(m.get("body", b"") for m in messages
                        if m["type"] == "http.response.body")
        return start["status"], dict(start["headers"]), json.loads(data)

    def test_private_endpoints_require_internal_bearer(self):
        for auth in (None, "incorrect-secret"):
            for action, payload in (
                ("issue", {"order_id": ORDER, "email": EMAIL}),
                ("redeem", {"order_id": ORDER, "recovery_token": "x" * 43}),
            ):
                code, _, body = self.request(action, payload, auth)
                self.assertEqual(code, 401)
                self.assertNotIn("delivery", body)
                self.assertNotIn("order_token", body)
        with Session(self.engine) as db:
            self.assertIsNone(db.execute(recovery_tokens.select()).first())

    def test_issue_redeem_and_replay(self):
        code, headers, body = self.request("issue", {"order_id": ORDER, "email": EMAIL})
        self.assertEqual(code, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        delivery = body["delivery"]
        self.assertEqual(delivery["recipient"], EMAIL)
        payload = {"order_id": ORDER, "recovery_token": delivery["recovery_token"]}
        code, headers, body = self.request("redeem", payload)
        self.assertEqual(code, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        with Session(self.engine) as db:
            order = db.get(Order, ORDER)
            self.assertTrue(verify_token(body["order_token"], order.access_token_hash))
            self.assertFalse(verify_token(OLD, order.access_token_hash))
        code, _, body = self.request("redeem", payload)
        self.assertEqual(code, 400)
        self.assertNotIn("order_token", body)

    def test_unknown_and_wrong_address_are_indistinguishable(self):
        for payload in ({"order_id": ORDER, "email": "other@example.com"},
                        {"order_id": "UNKNOWN", "email": EMAIL}):
            code, _, body = self.request("issue", payload)
            self.assertEqual((code, body), (200, {"delivery": None}))

    def test_unconfigured_service_fails_closed(self):
        self.app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            internal_service_token=None)
        code, _, body = self.request("issue", {"order_id": ORDER, "email": EMAIL})
        self.assertEqual(code, 503)
        self.assertNotIn("delivery", body)


if __name__ == "__main__":
    unittest.main()
