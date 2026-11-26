"""Recovery body limits exercised at the actual FastAPI route boundary."""
import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from pydantic import SecretStr
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.db.session import get_db
from render_public_recovery import router as public
from render_recovery_routes import router as private
from render_sensitive_http import RECOVERY_BODY_LIMIT


class RecoveryBodyLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(public, prefix="/v1")
        self.app.include_router(private, prefix="/v1")
        self.db = Mock()
        self.app.dependency_overrides[get_db] = lambda: self.db()
        self.app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
            internal_service_token=SecretStr("fictional-auth"))

    def request(self, chunks, lengths=(), path="/v1/recovery/request"):
        messages = []
        reads = 0
        headers = [(b"content-type", b"application/json"),
                   (b"authorization", b"Bearer fictional-auth")]
        headers.extend((b"content-length", x) for x in lengths)
        scope = {"type":"http","asgi":{"version":"3.0"},"http_version":"1.1",
                 "method":"POST","scheme":"http","path":path,"raw_path":path.encode(),
                 "query_string":b"","root_path":"","headers":headers,
                 "client":("192.0.2.1",12345),"server":("localhost",80)}
        async def receive():
            nonlocal reads
            if reads >= len(chunks):
                return {"type":"http.disconnect"}
            chunk = chunks[reads]
            reads += 1
            return {"type":"http.request","body":chunk,"more_body":reads<len(chunks)}
        async def send(msg):
            messages.append(msg)
        asyncio.run(self.app(scope,receive,send))
        start = next(m for m in messages if m["type"]=="http.response.start")
        data = b"".join(m.get("body",b"") for m in messages if m["type"]=="http.response.body")
        self.assertEqual(dict(start["headers"])[b"cache-control"],b"no-store")
        return start["status"], json.loads(data), reads

    def test_declared_oversize_rejected_before_body_read(self):
        code, body, reads = self.request([b"secret"], [b"4097"])
        self.assertEqual((code, body, reads), (413, {"detail":"Request too large."},0))
        self.db.assert_not_called()

    def test_chunked_oversize_rejected_at_limit(self):
        code, body, reads = self.request([b"x"*2048,b"x"*2048,b"x",b"secret"])
        self.assertEqual((code,body,reads),(413,{"detail":"Request too large."},3))
        self.db.assert_not_called()

    def test_invalid_or_mismatched_length_rejected(self):
        for lengths in ([b"-1"],[b"4",b"4"],[b"4"]):
            code,body,_ = self.request([b"{}"],lengths)
            self.assertEqual((code,body),(400,{"detail":"Invalid request."}))
        self.db.assert_not_called()

    def test_private_recovery_also_bounded(self):
        code,body,_ = self.request([b"x"*4097],path="/v1/internal/recovery/redeem")
        self.assertEqual((code,body),(413,{"detail":"Request too large."}))
        self.db.assert_not_called()

    def test_valid_json_at_limit_reaches_disabled_service(self):
        body = json.dumps({"order_id":"ZJ-TEST","email":"buyer@example.com"}).encode()
        body += b" "*(RECOVERY_BODY_LIMIT-len(body))
        code,data,_ = self.request([body[:2000],body[2000:]], [b"4096"])
        self.assertEqual((code,data),(503,{"detail":"Recovery unavailable."}))
