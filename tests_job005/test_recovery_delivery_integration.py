"""Public recovery + actual private n8n transport, fictional order only."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import unittest

from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import get_db
from app.models import Order, OrderStatus
from app.security.tokens import hash_token, verify_token, utcnow
from render_recovery import recovery_tokens
from render_recovery_limits import recovery_limits
from render_recovery_delivery import deliver_sandbox_recovery
from render_public_recovery import router, PublicRecoveryConfig, get_public_recovery_config

URL = os.environ.get("TEST_RECOVERY_DATABASE_URL")


@unittest.skipUnless(URL, "requires disposable PostgreSQL")
@unittest.skipUnless(os.environ.get("TEST_RECOVERY_SOCKET"), "requires private sandbox relay")
class RecoveryDeliveryIntegrationTests(unittest.TestCase):
    def test_public_recovery_through_n8n_and_redeem(self):
        url = make_url(URL)
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.host, "127.0.0.1")
        self.assertEqual(url.database, "zunpy_recovery_test")
        admin = create_engine(url)
        self.addCleanup(admin.dispose)
        with admin.begin() as conn:
            conn.execute(text("CREATE SCHEMA zunpy_delivery_test"))
        engine = create_engine(url, connect_args={"options":
            "-c search_path=zunpy_delivery_test -c statement_timeout=10000"})
        self.addCleanup(engine.dispose)
        Order.__table__.create(engine)
        recovery_tokens.create(engine)
        recovery_limits.create(engine)
        order_id = "ZJ-RECOVERY-TEST"
        email = "buyer@example.com"
        old = "fictional-original-access"
        now = utcnow()
        with Session(engine) as db, db.begin():
            db.add(Order(
                order_id=order_id, customer_email=email, status=OrderStatus.WAITING_UPLOAD,
                payment_provider="paypal", payment_reference="PAYPAL:PUBLICTEST",
                amount_cents=2900, currency="EUR", max_documents=1,
                access_token_hash=hash_token(old),
                access_expires_at=now + timedelta(days=1),
                upload_expires_at=now + timedelta(hours=1),
            ))

        app = FastAPI()
        app.include_router(router, prefix="/v1")
        def get_test_db():
            with Session(engine) as db:
                yield db
        app.dependency_overrides[get_db] = get_test_db
        delivered = []

        def request(action, payload):
            path = "/v1/recovery/" + action
            body = json.dumps(payload).encode()
            scope = {
                "type":"http", "asgi":{"version":"3.0"}, "http_version":"1.1",
                "method":"POST", "scheme":"http", "path":path,
                "raw_path":path.encode(), "query_string":b"", "root_path":"",
                "headers":[(b"content-type",b"application/json"),
                           (b"x-forwarded-for",b"203.0.113.50")],
                "client":("192.0.2.42",12345), "server":("localhost",80),
            }
            messages = []
            async def receive():
                return {"type":"http.request","body":body,"more_body":False}
            async def send(message):
                messages.append(message)
            asyncio.run(app(scope, receive, send))
            start = next(m for m in messages if m["type"] == "http.response.start")
            data = b"".join(m.get("body",b"") for m in messages if m["type"] == "http.response.body")
            self.assertEqual(dict(start["headers"])[b"cache-control"], b"no-store")
            return start["status"], json.loads(data)

        good = {"order_id":order_id,"email":email}
        self.assertEqual(request("request",good)[0],503)
        secret = Path("/run/zunpy-recovery-secret").read_text().strip()
        def deliver(delivery):
            deliver_sandbox_recovery(delivery, socket_path=os.environ["TEST_RECOVERY_SOCKET"], secret=secret)
            delivered.append(delivery)
        config = PublicRecoveryConfig(b"x"*32, deliver)
        app.dependency_overrides[get_public_recovery_config] = lambda: config
        expected = (202,{"status":"accepted"})
        self.assertEqual(request("request",{"order_id":"UNKNOWN","email":email}),expected)
        self.assertEqual(request("request",{"order_id":order_id,"email":"wrong@example.com"}),expected)
        self.assertEqual(delivered,[])
        self.assertEqual(request("request",good),expected)
        self.assertEqual(request("request",good),expected)
        self.assertEqual(request("request",good),expected)
        self.assertEqual(len(delivered),1)
        self.assertEqual(delivered[0].recipient,email)
        with Session(engine) as db:
            from sqlalchemy import select
            attempts = db.execute(select(recovery_limits.c.attempts).where(
                recovery_limits.c.quota_key.like("order:%"))).scalars().all()
            self.assertIn(3, attempts)
        token = delivered[0].raw_token
        self.assertEqual(request("redeem",{"order_id":order_id,"recovery_token":"x"*43})[0],400)
        code, data = request("redeem",{"order_id":order_id,"recovery_token":token})
        self.assertEqual(code,200)
        with Session(engine) as db:
            order = db.get(Order,order_id)
            self.assertTrue(verify_token(data["order_token"],order.access_token_hash))
            self.assertFalse(verify_token(old,order.access_token_hash))
            self.assertEqual(order.access_expires_at, now + timedelta(days=1))
            self.assertEqual(order.upload_expires_at, now + timedelta(hours=1))
        self.assertEqual(request("redeem",{"order_id":order_id,"recovery_token":token})[0],400)


if __name__ == "__main__":
    unittest.main()
