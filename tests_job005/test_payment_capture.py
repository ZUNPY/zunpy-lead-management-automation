"""Offline JOB-005 payment tests. Run: python -m unittest discover -s tests_job005 -v"""
import copy
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

# The Render build reconstructs the app from ZIP parts. Only Settings is
# imported by this module; fake that type to test the actual payment override.
config = types.ModuleType("app.core.config")
config.Settings = object
path = Path(__file__).resolve().parents[1] / "render_payments.py"
spec = importlib.util.spec_from_file_location("job005_payments", path)
payments = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"app.core.config": config, spec.name: payments}):
    spec.loader.exec_module(payments)

CLAIM = "fictional-test-claim-0123456789"
ORDER = "SANDBOXTEST001"


def approved():
    return {
        "id": ORDER, "intent": "CAPTURE", "status": "APPROVED",
        "purchase_units": [{
            "reference_id": "ZUNPY-JOB001",
            "custom_id": "ZUNPY:" + CLAIM,
            "amount": {"currency_code": "EUR", "value": "29.00"},
        }],
        "payer": {"email_address": "buyer@example.com"},
    }


def completed():
    payload = approved()
    payload["status"] = "COMPLETED"
    payload["purchase_units"][0]["payments"] = {"captures": [{
        "id": "TESTCAPTURE01", "status": "COMPLETED",
        "amount": {"currency_code": "EUR", "value": "29.00"},
    }]}
    return payload


class CaptureSecurityTests(unittest.TestCase):
    def invoke(self, responses, claim=CLAIM):
        with patch.object(payments, "_bearer_headers", return_value={}), \
             patch.object(payments, "_api_base_url", return_value="https://api-m.sandbox.paypal.com"), \
             patch.object(payments, "_request_json", side_effect=responses) as http:
            self.http = http
            return payments.capture_paypal_order(
                object(), paypal_order_id=ORDER, claim_secret=claim,
                expected_amount_cents=2900, expected_currency="EUR",
            )

    def methods(self):
        return [c.kwargs["method"] for c in self.http.call_args_list]

    def test_invalid_orders_never_capture(self):
        cases = []
        cases.append(("wrong claim", approved(), "wrong-test-secret-123456"))
        for field, value in [("id", "OTHER"), ("intent", "AUTHORIZE"), ("status", "CREATED")]:
            p = approved()
            p[field] = value
            cases.append((field, p, CLAIM))
        for field, value in [("reference_id", "OTHER"), ("amount", {"currency_code":"USD","value":"29.00"}), ("amount", {"currency_code":"EUR","value":"1.00"}), ("amount", {"currency_code":"EUR","value":"NaN"})]:
            p = approved()
            p["purchase_units"][0][field] = value
            cases.append((str(value), p, CLAIM))
        for name, payload, claim in cases:
            with self.subTest(name=name):
                with self.assertRaises(payments.PaymentValidationError):
                    self.invoke([payload], claim)
                self.assertEqual(self.methods(), ["GET"])

    def test_approved_order_captures_once(self):
        result = self.invoke([approved(), completed()])
        self.assertEqual(self.methods(), ["GET", "POST"])
        self.assertEqual(result.amount_cents, 2900)

    def test_completed_order_does_not_capture_again(self):
        self.assertEqual(self.invoke([completed()]).capture_id, "TESTCAPTURE01")
        self.assertEqual(self.methods(), ["GET"])

    def test_ambiguous_capture_recovers_by_get(self):
        result = self.invoke([approved(), payments.PaymentProviderError("timeout"), completed()])
        self.assertEqual(result.order_id, ORDER)
        self.assertEqual(self.methods(), ["GET", "POST", "GET"])

    def test_wrong_capture_amount_rejected(self):
        p = completed()
        p["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"] = "1.00"
        with self.assertRaises(payments.PaymentValidationError):
            self.invoke([approved(), p, copy.deepcopy(p)])
        self.assertEqual(self.methods(), ["GET", "POST", "GET"])


class RecoverySecurityTests(unittest.TestCase):
    def invoke(self, payload, claim=CLAIM):
        with patch.object(payments, "_bearer_headers", return_value={}), \
             patch.object(payments, "_api_base_url", return_value="https://api-m.sandbox.paypal.com"), \
             patch.object(payments, "_request_json", return_value=payload) as http:
            self.http = http
            return payments.recover_completed_paypal_order(
                object(), paypal_order_id=ORDER, claim_secret=claim,
                expected_amount_cents=2900, expected_currency="EUR",
            )

    def test_create_does_not_send_plaintext_claim(self):
        with patch.object(payments, "_bearer_headers", return_value={}), \
             patch.object(payments, "_api_base_url", return_value="https://api-m.sandbox.paypal.com"), \
             patch.object(payments, "_request_json", return_value={"id": ORDER}) as http:
            payments.create_paypal_order(object(), amount_cents=2900,
                                         currency="EUR", claim_secret=CLAIM)
            request = http.call_args.kwargs
            body = payments.json.loads(request["data"])
            self.assertEqual(body["purchase_units"][0]["custom_id"],
                             payments._claim_custom_id(CLAIM))
            self.assertNotIn(CLAIM, request["data"].decode())
            self.assertNotIn(CLAIM, request["headers"]["PayPal-Request-Id"])

    def test_hashed_claim_cannot_be_used_as_plaintext(self):
        value = payments._claim_custom_id(CLAIM)
        self.assertTrue(payments._claim_matches(value, CLAIM))
        self.assertFalse(payments._claim_matches(value, value.removeprefix("ZUNPY:")))

    def test_recover_completed_order_only_uses_get(self):
        p = completed()
        p["purchase_units"][0]["custom_id"] = payments._claim_custom_id(CLAIM)
        self.assertEqual(self.invoke(p).capture_id, "TESTCAPTURE01")
        self.assertEqual([c.kwargs["method"] for c in self.http.call_args_list], ["GET"])

    def test_recovery_rejects_unapproved_legacy_or_invalid_claims(self):
        for p, claim in [(approved(), CLAIM), (completed(), CLAIM)]:
            with self.assertRaises(payments.PaymentValidationError):
                self.invoke(p, claim)
            self.assertEqual(self.http.call_count, 1)
        p = approved()
        p["purchase_units"][0]["custom_id"] = payments._claim_custom_id(CLAIM)
        with self.assertRaises(payments.PaymentValidationError):
            self.invoke(p)
        self.assertEqual(self.http.call_count, 1)
        p = completed()
        p["purchase_units"][0]["custom_id"] = payments._claim_custom_id(CLAIM)
        with self.assertRaises(payments.PaymentValidationError):
            self.invoke(p, "wrong-secret")
        self.assertEqual(self.http.call_count, 1)


if __name__ == "__main__":
    unittest.main()
