"""Offline service tests; SQLite exercises persistence, not PostgreSQL locking."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_recovery as recovery
from app.models import Order, OrderStatus
from app.security.tokens import hash_token, verify_token, ensure_aware_utc

NOW = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
ORDER = "ZJ-RECOVERY-TEST"
EMAIL = "buyer@example.com"
OLD = "fictional-original-token"
ACCESS = NOW + timedelta(days=2)
UPLOAD = NOW + timedelta(hours=6)


class OrderRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Order.__table__.create(self.engine)
        recovery.recovery_tokens.create(self.engine)
        self.db = Session(self.engine)
        self.db.add(Order(
            order_id=ORDER, customer_email=EMAIL,
            payment_provider="paypal", payment_reference="PAYPAL:TESTORDER001",
            amount_cents=2900, currency="EUR", max_documents=1,
            status=OrderStatus.WAITING_UPLOAD, access_token_hash=hash_token(OLD),
            access_expires_at=ACCESS, upload_expires_at=UPLOAD,
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def issue(self, email=EMAIL, now=NOW):
        result = recovery.issue_recovery(self.db, order_id=ORDER, email=email, now=now)
        self.db.commit()
        return result

    def redeem(self, token, now=NOW):
        result = recovery.redeem_recovery(self.db, order_id=ORDER, raw_token=token, now=now)
        self.db.commit()
        return result

    def row(self):
        return self.db.execute(select(recovery.recovery_tokens)).mappings().one_or_none()

    def test_single_use_and_credential_rotation(self):
        delivery = self.issue()
        self.assertEqual(delivery.recipient, EMAIL)
        self.assertEqual(delivery.expires_at, NOW + timedelta(minutes=15))
        self.assertEqual(self.row()["token_hash"], hash_token(delivery.raw_token))
        self.assertNotEqual(self.row()["token_hash"], delivery.raw_token)
        result = self.redeem(delivery.raw_token)
        order = self.db.get(Order, ORDER)
        self.assertTrue(verify_token(result.order_token, order.access_token_hash))
        self.assertFalse(verify_token(OLD, order.access_token_hash))
        self.assertEqual(ensure_aware_utc(order.access_expires_at), ACCESS)
        self.assertEqual(ensure_aware_utc(order.upload_expires_at), UPLOAD)
        self.assertIsNone(self.redeem(delivery.raw_token))
        self.assertIsNotNone(self.row()["consumed_at"])

    def test_wrong_email_and_unknown_order(self):
        self.assertIsNone(self.issue("other@example.com"))
        self.assertIsNone(recovery.issue_recovery(
            self.db, order_id="MISSING", email=EMAIL, now=NOW))
        self.assertIsNone(self.row())

    def test_duplicate_request_and_wrong_token_preserve_link(self):
        delivery = self.issue()
        self.assertIsNone(self.issue())
        self.assertIsNone(self.redeem("wrong-token"))
        self.assertIsNotNone(self.redeem(delivery.raw_token))

    def test_expired_token_and_reissue(self):
        delivery = self.issue()
        later = NOW + timedelta(minutes=15)
        self.assertIsNone(self.redeem(delivery.raw_token, later))
        replacement = self.issue(now=later)
        self.assertIsNotNone(replacement)
        self.assertIsNone(self.redeem(delivery.raw_token, later))
        self.assertIsNotNone(self.redeem(replacement.raw_token, later))

    def test_claim_rotation_invalidates_pending_link(self):
        delivery = self.issue()
        order = self.db.get(Order, ORDER)
        order.access_token_hash = hash_token("replacement")
        self.db.commit()
        self.assertIsNone(self.redeem(delivery.raw_token))

    def test_ineligible_order(self):
        order = self.db.get(Order, ORDER)
        for state in (OrderStatus.PAID, OrderStatus.REFUNDED,
                      OrderStatus.FAILED, OrderStatus.CANCELLED):
            order.status = state
            self.db.commit()
            self.assertIsNone(self.issue())
        order.status = OrderStatus.WAITING_UPLOAD
        order.payment_reference = "JOB002-TEST"
        self.db.commit()
        self.assertIsNone(self.issue())
        self.assertIsNone(self.row())

    def test_access_deadline_bounds_recovery(self):
        order = self.db.get(Order, ORDER)
        order.access_expires_at = NOW + timedelta(minutes=2)
        self.db.commit()
        delivery = self.issue()
        self.assertEqual(delivery.expires_at, NOW + timedelta(minutes=2))
        self.assertIsNone(self.redeem(delivery.raw_token, delivery.expires_at))
        self.assertIsNone(self.issue(now=delivery.expires_at))

    def test_redemption_rollback_preserves_original_token(self):
        delivery = self.issue()
        self.assertIsNotNone(recovery.redeem_recovery(
            self.db, order_id=ORDER, raw_token=delivery.raw_token, now=NOW))
        self.db.rollback()
        self.assertTrue(verify_token(OLD, self.db.get(Order, ORDER).access_token_hash))
        self.assertIsNone(self.row()["consumed_at"])
        self.assertIsNotNone(self.redeem(delivery.raw_token))


if __name__ == "__main__":
    unittest.main()
