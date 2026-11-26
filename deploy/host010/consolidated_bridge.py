#!/usr/bin/env python3
"""HOST-010.8: single authenticated dispatcher for the four verified fixed missions."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = Path(__file__).resolve().parent
PORT = 18770
# Git blob identities of the exact previously verified implementations.
PINNED = {
    "probe_hermes_acp.py": "6a25e0723561a2a6a45701a9324753c66e06b04d",
    "inference_bridge.py": "f84edab4c8bf9ab196324319b750e075fdbdf278",
    "review_bridge_v031.py": "41c6964bc1537862cb738319dba18dd6e0be75ac",
    "patch_bridge.py": "150156a84a90bf4b65212ce12df02118b12cbd8d",
}

def verify_modules():
    for name, expected in PINNED.items():
        path = HERE / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Missing or invalid pinned module")
        raw = path.read_bytes()
        if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != expected:
            raise RuntimeError("Pinned module integrity mismatch: " + name)
        compile(raw, str(path), "exec")

def initialize():
    result = subprocess.run(
        [sys.executable, str(HERE / "probe_hermes_acp.py")],
        cwd=HERE, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=40, check=False)
    if result.returncode != 0 or result.stdout.decode("utf-8", errors="replace").splitlines() != [
            "ACP_PROTOCOL_VERSION: 1", "ACP_INITIALIZE: PASS", "HOST-010.2 ACP_TRANSPORT: PASS"]:
        raise RuntimeError("ACP initialize blocked")
    return {"mission":"acp.initialize","status":"verified","protocolVersion":1,"inference":False}

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key")
        result[key] = value
    return result

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
        payload = json.dumps(data, separators=(",",":"), allow_nan=False).encode()
        self.close_connection = True
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        except OSError:
            pass

    def do_POST(self):
        if self.path != "/mission":
            return self.reply(404, {"status":"not_found"})
        keys = self.headers.get_all("X-ZUNPY-Hermes-Auth", [])
        if len(keys) != 1 or not hmac.compare_digest(keys[0].encode("utf-8"), self.server.secret):
            return self.reply(403, {"status":"denied"})
        lengths = self.headers.get_all("Content-Length", [])
        if (self.headers.get("Transfer-Encoding") or len(lengths) != 1
                or not re.fullmatch(r"[0-9]{1,3}", lengths[0])
                or not 1 <= int(lengths[0]) <= 256):
            return self.reply(400, {"status":"invalid_request"})
        try:
            body = self.rfile.read(int(lengths[0]))
            if len(body) != int(lengths[0]):
                raise ValueError
            obj = json.loads(body, object_pairs_hook=unique_object)
            if type(obj) is not dict or set(obj) != {"mission"} or type(obj["mission"]) is not str:
                raise ValueError
            mission = obj["mission"]
            if mission not in self.server.missions:
                raise ValueError
        except (ValueError, OSError):
            return self.reply(400, {"status":"invalid_mission"})
        try:
            self.connection.settimeout(200)
            verify_modules()
            result = self.server.missions[mission]()
            if (type(result) is not dict or result.get("mission") != mission
                    or result.get("status") != "verified" or result.get("protocolVersion") != 1):
                raise RuntimeError("Unexpected mission result")
        except Exception as exc:
            print("HOST-010.8 BLOCKED:", mission, type(exc).__name__, flush=True)
            return self.reply(503, {"mission":mission,"status":"blocked"})
        return self.reply(200, result)

def main():
    verify_modules()
    # Import the verified modules, without launching their HTTP servers.
    import inference_bridge as inference
    import review_bridge_v031 as review
    import patch_bridge as patch
    inference.interpreter()
    review.read_fixture()
    patch.read_fixture()
    secret = inference.secret()
    with Server(("127.0.0.1", PORT), Handler) as server:
        server.secret = secret
        server.missions = {
            "acp.initialize": initialize,
            "acp.inference": inference.probe,
            "acp.review_invoice_fixture": review.probe,
            "acp.patch_invoice_fixture": patch.probe,
        }
        print("HOST-010.8 CONSOLIDATED_BRIDGE_READY: 127.0.0.1:18770", flush=True)
        print("Fixed missions: 4 | Pinned modules: PASS | Serial execution", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("Unsupported arguments")
    main()
