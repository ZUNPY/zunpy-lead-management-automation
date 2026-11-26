"""Offline checkout retry lifecycle with a real isolated order database."""
from datetime import timedelta
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_paypal as checkout
from render_recovery import issue_recovery, redeem_recovery, recovery_tokens
from app.models import Order, OrderStatus
from app.security.tokens import hash_token, verify_token, ensure_aware_utc, utcnow


class CheckoutRetryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Order.__table__.create(self.engine)
        recovery_tokens.create(self.engine)
        now = utcnow()
        self.access_deadline = now + timedelta(days=2)
        self.upload_deadline = now + timedelta(hours=6)
        self.order_id = "ZJ-RETRY-TEST"
        self.old_token = "fictional-original-access"
        self.email = "buyer@example.com"
        with Session(self.engine) as db, db.begin():
            db.add(Order(
                order_id=self.order_id, customer_email=self.email,
                status=OrderStatus.WAITING_UPLOAD, payment_provider="paypal",
                payment_reference="PAYPAL:CHECKOUTTEST", amount_cents=2900,
                currency="EUR", max_documents=1,
                access_token_hash=hash_token(self.old_token),
                access_expires_at=self.access_deadline,
                upload_expires_at=self.upload_deadline,
            ))
        self.verified = SimpleNamespace(order_id="CHECKOUTTEST", capture_id="CAPTURETEST",
                                        payer_email=self.email, amount_cents=2900, currency="EUR")

    def retry(self):
        with patch.object(checkout, "capture_paypal_order", return_value=self.verified), \
             patch.object(checkout, "issue_order_token") as issue, \
             Session(self.engine) as db:
            result = checkout.capture_checkout_order(
                "CHECKOUTTEST", checkout.PayPalCapturePayload(claim_secret="x"*32),
                db=db, settings=SimpleNamespace(),
            )
            issue.assert_not_called()
            return result

    def assert_unchanged(self, token):
        with Session(self.engine) as db:
            order = db.get(Order, self.order_id)
            self.assertTrue(verify_token(token, order.access_token_hash))
            self.assertEqual(ensure_aware_utc(order.access_expires_at), self.access_deadline)
            self.assertEqual(ensure_aware_utc(order.upload_expires_at), self.upload_deadline)

    def test_retry_cannot_replace_original_or_recovered_access(self):
        result = self.retry()
        self.assertEqual(result["result"], "paypal_order_recovery_required")
        self.assertEqual(result["order_id"], self.order_id)
        self.assertNotIn("order_token", result)
        self.assert_unchanged(self.old_token)
        with Session(self.engine) as db, db.begin():
            link = issue_recovery(db, order_id=self.order_id, email=self.email)
        self.assertIsNotNone(link)
        self.assertNotIn("order_token", self.retry())
        with Session(self.engine) as db, db.begin():
            access = redeem_recovery(db, order_id=self.order_id, raw_token=link.raw_token)
        self.assertIsNotNone(access)
        self.assertNotIn("order_token", self.retry())
        self.assert_unchanged(access.order_token)

    def test_expired_and_partial_orders_are_not_reactivated(self):
        for status, expiry in (
            (OrderStatus.WAITING_UPLOAD, utcnow()-timedelta(seconds=1)),
            (OrderStatus.PAID, self.access_deadline),
            (OrderStatus.CANCELLED, self.access_deadline),
        ):
            with self.subTest(status=status):
                with Session(self.engine) as db, db.begin():
                    order = db.get(Order, self.order_id)
                    order.status = status
                    order.access_expires_at = expiry
                with self.assertRaises(HTTPException) as error:
                    self.retry()
                self.assertEqual(error.exception.status_code, 409)
                with Session(self.engine) as db:
                    order = db.get(Order, self.order_id)
                    self.assertEqual(order.status, status)
                    self.assertEqual(ensure_aware_utc(order.access_expires_at), expiry)
                    self.assertTrue(verify_token(self.old_token, order.access_token_hash))

    def test_mismatched_payer_cannot_retrieve_existing_order(self):
        self.verified.payer_email = "other@example.com"
        with self.assertRaises(HTTPException) as error:
            self.retry()
        self.assertEqual(error.exception.status_code, 409)
        self.assert_unchanged(self.old_token)
