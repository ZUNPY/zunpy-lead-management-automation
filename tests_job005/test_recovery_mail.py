"""Candidate mail contract tests. No real mail, network or credentials."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_recovery_mail as mail


class RecoveryMailTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
        self.delivery = SimpleNamespace(
            order_id="ZJ-0123456789ABCDEF", recipient="buyer+test@example.com",
            raw_token="x"*43, expires_at=self.now+timedelta(minutes=10))
        self.secret = "a"*64
        self.patcher = patch.object(mail, "UnixHTTPConnection")
        self.connection = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.conn = self.connection.return_value
        self.response = MagicMock()
        self.response.status = 200
        self.response.read.return_value = b'{"status":"accepted"}'
        self.conn.getresponse.return_value.__enter__.return_value = self.response

    def send(self, **kwargs):
        options = dict(socket_path="/relay/mail.sock", secret=self.secret, now=self.now)
        options.update(kwargs)
        mail.deliver_recovery_mail(self.delivery, **options)

    def test_valid_single_mailbox_and_exact_ack(self):
        self.send()
        self.connection.assert_called_once_with("/relay/mail.sock", timeout=35)
        self.conn.request.assert_called_once()
        args, kwargs = self.conn.request.call_args
        self.assertEqual(args, ("POST", mail.PRODUCTION_PATH))
        self.assertEqual(json.loads(kwargs["body"]), {
            "order_id": self.delivery.order_id,
            "recipient": self.delivery.recipient,
            "recovery_token": self.delivery.raw_token,
            "expires_at": self.delivery.expires_at.isoformat(),
        })
        self.assertEqual(kwargs["headers"]["X-ZUNPY-Recovery-Auth"], self.secret)
        self.conn.close.assert_called_once()

    def test_invalid_recipients_never_reach_transport(self):
        for value in ("a@example.com,b@example.com", "A <a@example.com>",
                      "a@example.com\r\nBcc: b@example.com", "a b@example.com",
                      "a..b@example.com", "a@-example.com", "a@example",
                      "é@example.com", "a"*65+"@example.com"):
            with self.subTest(value=value):
                self.delivery.recipient = value
                with self.assertRaises(ValueError):
                    self.send()
        self.connection.assert_not_called()

    def test_invalid_credentials_and_expiry_never_reach_transport(self):
        for field, value in (
            ("order_id","ZJ-RECOVERY-TEST"), ("raw_token","short"),
            ("expires_at",self.now), ("expires_at",self.now+timedelta(minutes=16)),
            ("expires_at",self.now.replace(tzinfo=None)),
        ):
            with self.subTest(field=field):
                previous = getattr(self.delivery,field)
                setattr(self.delivery,field,value)
                with self.assertRaises(ValueError):
                    self.send()
                setattr(self.delivery,field,previous)
        for options in ({"secret":"invalid"}, {"socket_path":"relative.sock"}):
            with self.assertRaises(ValueError):
                self.send(**options)
        self.connection.assert_not_called()

    def test_http_or_ack_failure_not_retried(self):
        for status, body in [(503,b'{"status":"accepted"}'), (200,b''),
            (200,b'{"status":"accepted","secret":"private"}'),
            (200,b'{"status":"rejected"}'), (200,b'x'*257)]:
            self.conn.reset_mock()
            self.response.status = status
            self.response.read.return_value = body
            with self.assertRaisesRegex(mail.RecoveryMailError,
                                       "^Recovery mail delivery unconfirmed.$"):
                self.send()
            self.conn.request.assert_called_once()
            self.conn.close.assert_called_once()

    def test_ambiguous_transport_failure_is_redacted_without_retry(self):
        self.conn.request.side_effect = TimeoutError("private synthetic credential")
        with self.assertRaises(mail.RecoveryMailError) as ctx:
            self.send()
        self.assertEqual(str(ctx.exception), "Recovery mail delivery unconfirmed.")
        self.assertTrue(ctx.exception.__suppress_context__)
        self.conn.request.assert_called_once()
        self.conn.close.assert_called_once()
