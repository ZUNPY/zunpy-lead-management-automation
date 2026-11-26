#!/usr/bin/env python3
"""HOST-010 fixed-mission bridge. No caller-supplied commands or prompts."""
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PORT = 18766
EXPECTED = {"mission": "acp.initialize"}

def read_secret():
    path = ROOT / "bridge-secret"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise RuntimeError("Unsafe bridge credential")
        raw = f.read(66)
    if not re.fullmatch(rb"[0-9a-f]{64}\n?", raw):
        raise RuntimeError("Invalid bridge credential")
    return raw.strip()

class Server(HTTPServer):
    allow_reuse_address = True
    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(5)
        return sock, address

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, data):
        payload = json.dumps(data, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_POST(self):
        if self.path != "/mission":
            return self.reply(404, {"status":"not_found"})
        keys = self.headers.get_all("X-ZUNPY-Hermes-Auth", [])
        if len(keys) != 1 or not hmac.compare_digest(
                keys[0].encode("utf-8"), self.server.secret):
            return self.reply(403, {"status":"denied"})
        lengths = self.headers.get_all("Content-Length", [])
        if (self.headers.get("Transfer-Encoding") or len(lengths)!=1
                or not re.fullmatch(r"[0-9]{1,3}", lengths[0])
                or not 1 <= int(lengths[0]) <= 256):
            return self.reply(400, {"status":"invalid_request"})
        try:
            body = self.rfile.read(int(lengths[0]))
            if len(body) != int(lengths[0]) or json.loads(body) != EXPECTED:
                raise ValueError
        except (ValueError, OSError):
            return self.reply(400, {"status":"invalid_mission"})
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT/"probe_hermes_acp.py")],
                cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=40, check=False)
            if (result.returncode != 0 or
                    result.stdout.decode("utf-8", errors="replace").splitlines() != [
                        "ACP_PROTOCOL_VERSION: 1",
                        "ACP_INITIALIZE: PASS",
                        "HOST-010.2 ACP_TRANSPORT: PASS"]):
                raise RuntimeError
        except (OSError, subprocess.SubprocessError, RuntimeError):
            return self.reply(503, {"mission":"acp.initialize","status":"blocked"})
        return self.reply(200, {"mission":"acp.initialize","status":"verified",
                                "protocolVersion":1,"inference":False})

if __name__=="__main__":
    secret = read_secret()
    with Server(("127.0.0.1", PORT), Handler) as server:
        server.secret = secret
        print("HOST-010.3 BRIDGE_READY: 127.0.0.1:"+str(PORT), flush=True)
        print("Fixed mission only: acp.initialize; no inference", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
