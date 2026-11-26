"""Explicit recovery assembly with a real local Unix transport; no Gmail."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socketserver
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_public_recovery as public
from render_recovery import RecoveryDelivery
from render_recovery_mail import RecoveryMailError, PRODUCTION_PATH


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline().decode().strip()
        headers = {}
        while True:
            line_header = self.rfile.readline()
            if line_header in (b"\r\n", b""):
                break
            key, value = line_header.decode().split(":", 1)
            headers[key.lower()] = value.strip()
        body = json.loads(self.rfile.read(int(headers["content-length"])))
        self.server.received.append((line, headers, body))
        ack = self.server.ack
        self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         + b"Content-Length: " + str(len(ack)).encode()
                         + b"\r\nConnection: close\r\n\r\n" + ack)


class RecoveryAssemblyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "source"
        self.mail = self.root / "mail"
        self.sock = self.root / "mail.sock"
        for file, value in ((self.source, "a"), (self.mail, "b")):
            file.write_text(value*64+"\n")
            file.chmod(0o600)
        self.server = socketserver.UnixStreamServer(str(self.sock), Handler)
        self.server.received = []
        self.server.ack = b'{"status":"accepted"}'
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.delivery = RecoveryDelivery(
            "ZJ-0123456789ABCDEF", "buyer@example.com", "x"*43,
            datetime.now(timezone.utc)+timedelta(minutes=10))

    def build(self, **overrides):
        args = dict(source_secret_file=str(self.source),
                    mail_secret_file=str(self.mail), socket_path=str(self.sock))
        args.update(overrides)
        return public.build_public_recovery_config(**args)

    def test_explicit_configuration_delivers_via_private_socket(self):
        config = self.build()
        self.assertEqual(config.source_secret, bytes.fromhex("a"*64))
        self.assertNotIn("b"*64, repr(config))
        config.deliver(self.delivery)
        self.assertEqual(len(self.server.received), 1)
        line, headers, body = self.server.received[0]
        self.assertEqual(line, "POST "+PRODUCTION_PATH+" HTTP/1.1")
        self.assertEqual(headers["x-zunpy-recovery-auth"], "b"*64)
        self.assertEqual(body, {"order_id": self.delivery.order_id,
                                "recipient": self.delivery.recipient,
                                "recovery_token": self.delivery.raw_token,
                                "expires_at": self.delivery.expires_at.isoformat()})

    def test_invalid_secret_files_fail_closed(self):
        self.mail.chmod(0o644)
        with self.assertRaises(ValueError):
            self.build()
        self.mail.chmod(0o600)
        self.mail.write_text("a"*64)
        with self.assertRaises(ValueError):
            self.build()
        self.mail.write_text("b"*65)
        with self.assertRaises(ValueError):
            self.build()
        alias = self.root / "alias"
        alias.symlink_to(self.source)
        with self.assertRaises(ValueError):
            self.build(mail_secret_file=str(alias))
        self.assertEqual(self.server.received, [])

    def test_missing_or_non_socket_fails_closed(self):
        for path in ("relative.sock", str(self.root/"absent"), str(self.source)):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.build(socket_path=path)
        self.assertEqual(self.server.received, [])

    def test_bad_ack_logs_generic_failure_without_retry(self):
        self.server.ack = b'{"status":"rejected"}'
        config = self.build()
        with self.assertLogs(public.logger, level="WARNING") as log:
            public._deliver_safely(config, self.delivery)
        self.assertEqual(len(self.server.received), 1)
        self.assertEqual(log.output, [
            "WARNING:render_public_recovery:Recovery delivery failed; link will expire normally."])

    def test_assembly_does_not_activate_public_dependency(self):
        with patch.dict(os.environ, {"RECOVERY_ENABLED":"1",
                                     "RECOVERY_MAIL_SOCKET":str(self.sock)}):
            self.build()
            self.assertIsNone(public.get_public_recovery_config())
        self.assertEqual(self.server.received, [])
