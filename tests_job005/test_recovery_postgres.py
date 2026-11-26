"""Integration test using a disposable PostgreSQL database, never production."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys
from threading import Barrier
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_recovery as recovery
from app.models import Order, OrderStatus
from app.security.tokens import hash_token, verify_token

URL = os.environ.get("TEST_RECOVERY_DATABASE_URL")


@unittest.skipUnless(URL, "requires disposable PostgreSQL")
class PostgreSQLRecoveryConcurrencyTests(unittest.TestCase):
    def test_concurrent_issue_and_redeem(self):
        url = make_url(URL)
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.host, "127.0.0.1")
        self.assertEqual(url.database, "zunpy_recovery_test")
        engine = create_engine(url, connect_args={
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        })
        self.addCleanup(engine.dispose)
        # Fail if this is not a fresh, dedicated test database.
        Order.__table__.create(engine)
        recovery.recovery_tokens.create(engine)
        now = datetime.now(timezone.utc)
        order_id = "ZJ-CONCURRENT-TEST"
        email = "buyer@example.com"
        old = "fictional-old-token"
        with Session(engine) as db, db.begin():
            db.add(Order(
                order_id=order_id, customer_email=email,
                payment_provider="paypal", payment_reference="PAYPAL:CONCURRENT01",
                amount_cents=2900, currency="EUR", max_documents=1,
                status=OrderStatus.WAITING_UPLOAD, access_token_hash=hash_token(old),
                access_expires_at=now + timedelta(days=1),
                upload_expires_at=now + timedelta(hours=1),
            ))

        def concurrent(operation):
            barrier = Barrier(2, timeout=10)

            def worker():
                with Session(engine) as db, db.begin():
                    # Establish two independent database connections first.
                    db.connection()
                    barrier.wait()
                    return operation(db)

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker) for _ in range(2)]
                return [future.result(timeout=20) for future in futures]

        deliveries = concurrent(lambda db: recovery.issue_recovery(
            db, order_id=order_id, email=email))
        valid = [item for item in deliveries if item is not None]
        self.assertEqual(len(valid), 1)
        raw = valid[0].raw_token
        accesses = concurrent(lambda db: recovery.redeem_recovery(
            db, order_id=order_id, raw_token=raw))
        valid = [item for item in accesses if item is not None]
        self.assertEqual(len(valid), 1)
        with Session(engine) as db:
            order = db.get(Order, order_id)
            self.assertTrue(verify_token(valid[0].order_token, order.access_token_hash))
            self.assertFalse(verify_token(old, order.access_token_hash))
            row = db.execute(select(recovery.recovery_tokens)).mappings().one()
            self.assertIsNotNone(row["consumed_at"])
            self.assertIsNone(recovery.redeem_recovery(
                db, order_id=order_id, raw_token=raw))


if __name__ == "__main__":
    unittest.main()
