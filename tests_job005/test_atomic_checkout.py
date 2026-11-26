"""Atomic checkout persistence on a disposable SQL database; PayPal mocked."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_paypal as checkout
from app.models import Order, OrderStatus
from app.security.tokens import verify_token


class AtomicCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        Order.metadata.create_all(self.engine)
        self.events = next(t for t in Order.metadata.tables.values()
                           if "event_type" in t.c and "order_id" in t.c)
        self.verified = SimpleNamespace(
            order_id="ATOMICCHECKOUT", capture_id="CAPTURETEST",
            payer_email="buyer@example.com", amount_cents=2900, currency="EUR")
        self.settings = SimpleNamespace(order_access_token_ttl_hours=48,
                                        order_upload_token_ttl_hours=24)

    def capture(self):
        with patch.object(checkout, "capture_paypal_order", return_value=self.verified), Session(self.engine) as db:
            return checkout.capture_checkout_order(
                "ATOMICCHECKOUT", checkout.PayPalCapturePayload(claim_secret="x"*32),
                db=db, settings=self.settings)

    def counts(self):
        with Session(self.engine) as db:
            return (db.scalar(select(func.count()).select_from(Order)),
                    db.scalar(select(func.count()).select_from(self.events)))

    def test_ready_order_and_both_audit_events_commit_together(self):
        result = self.capture()
        self.assertEqual(result["result"], "paypal_payment_verified_order_ready")
        self.assertEqual(self.counts(), (1, 2))
        with Session(self.engine) as db:
            order = db.get(Order, result["order_id"])
            self.assertEqual(order.status, OrderStatus.WAITING_UPLOAD)
            self.assertTrue(verify_token(result["order_token"], order.access_token_hash))
            types = set(db.scalars(select(self.events.c.event_type)))
            self.assertEqual(types, {"PAYMENT_CONFIRMED", "PAYPAL_PAYMENT_CAPTURED"})
        retry = self.capture()
        self.assertEqual(retry["result"], "paypal_order_recovery_required")
        self.assertEqual(retry["order_id"], result["order_id"])
        self.assertNotIn("order_token", retry)
        self.assertEqual(self.counts(), (1, 2))

    def test_interruption_before_second_audit_event_rolls_back_everything(self):
        original = checkout.add_event
        def interrupted(db, order_id, event_type, detail):
            if event_type == "PAYPAL_PAYMENT_CAPTURED":
                raise RuntimeError("synthetic interruption")
            original(db, order_id, event_type, detail)
            db.flush()
        with patch.object(checkout, "add_event", side_effect=interrupted):
            with self.assertRaises(HTTPException) as failure:
                self.capture()
        self.assertEqual(failure.exception.status_code, 503)
        self.assertEqual(self.counts(), (0, 0))
        self.capture()
        self.assertEqual(self.counts(), (1, 2))

    def test_legacy_paid_order_remains_for_manual_reconciliation(self):
        result = self.capture()
        with Session(self.engine) as db, db.begin():
            db.get(Order, result["order_id"]).status = OrderStatus.PAID
        with self.assertRaises(HTTPException) as failure:
            self.capture()
        self.assertEqual(failure.exception.status_code, 409)
        self.assertEqual(self.counts(), (1, 2))
        with Session(self.engine) as db:
            self.assertEqual(db.get(Order, result["order_id"]).status, OrderStatus.PAID)
