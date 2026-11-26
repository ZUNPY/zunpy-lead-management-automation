#!/usr/bin/env python3
"""HOST-011.4: five fixed missions, including independent CrewAI QA."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = Path(__file__).resolve().parent
PORT = 18770
QA_PYTHON = Path.home() / "proyectos/hermes_qwen_optimizer/.venv/bin/python"
QA_MISSION = "crewai.qa_invoice_fixture"
# Git blob identities of the exact previously verified implementations.
PINNED = {
    "probe_hermes_acp.py": "6a25e0723561a2a6a45701a9324753c66e06b04d",
    "inference_bridge_v051.py": "ee6f9a4aedd3f22150b1338b037715a661048e4e",
    "review_bridge_v051.py": "c4382c42982ff04620a7cfa6be780df77f15ba10",
    "patch_bridge_v051.py": "b90772327ccd28869814972882870fecf8921755",
    "qa_probe_v02.py": "440a45e8d6d4931981a762c1336d0ce344dca153",
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

def qa_probe():
    if not QA_PYTHON.is_file() or not os.access(QA_PYTHON, os.X_OK):
        raise RuntimeError("CrewAI interpreter unavailable")
    # Run the exact previously successful standalone probe in a new process group.
    env = {"HOME":str(Path.home()),"PATH":str(QA_PYTHON.parent)+":/usr/bin:/bin",
           "LANG":"C.UTF-8","PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1",
           "OTEL_SDK_DISABLED":"true","CREWAI_DISABLE_TELEMETRY":"true","NO_PROXY":"*"}
    child = subprocess.Popen([str(QA_PYTHON), "-B", str(HERE / "qa_probe_v02.py")],
                             cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    try:
        out, _ = child.communicate(timeout=160)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.communicate()
        raise RuntimeError("CrewAI QA timeout")
    if child.returncode != 0 or len(out) > 65536:
        raise RuntimeError("CrewAI QA blocked")
    prefix = "HOST-011.3 QA_PASS: "
    lines = [line[len(prefix):] for line in out.decode("utf-8").splitlines()
             if line.startswith(prefix)]
    if len(lines) != 1:
        raise RuntimeError("Missing unique QA result")
    r = json.loads(lines[0], object_pairs_hook=unique_object)
    if (type(r) is not dict or set(r) != {"crewaiVersion","modelConfigured","endpoint",
            "original","patched","reason","toolsConfigured"}
            or r["crewaiVersion"] != "1.15.28" or r["modelConfigured"] != "gemma4:26b"
            or r["endpoint"] != "http://127.0.0.1:11434/v1"
            or r["original"] != {"verdict":"REJECT","actual":79.0}
            or r["patched"] != {"verdict":"ACCEPT","actual":121.0}
            or type(r["reason"]) is not str or not 1 <= len(r["reason"].strip()) <= 400
            or type(r["toolsConfigured"]) is not int or r["toolsConfigured"] != 0):
        raise RuntimeError("Invalid QA evidence")
    return {"mission":QA_MISSION,"status":"verified","qaSchemaVersion":1,**r}

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
                    or result.get("status") != "verified"
                    or (mission == QA_MISSION and result.get("qaSchemaVersion") != 1)
                    or (mission != QA_MISSION and result.get("protocolVersion") != 1)):
                raise RuntimeError("Unexpected mission result")
        except Exception as exc:
            print("HOST-011.4 BLOCKED:", mission,
                  "ACP wire frame is not JSON" if type(exc) is RuntimeError and str(exc) == "ACP wire frame is not JSON" else type(exc).__name__, flush=True)
            return self.reply(503, {"mission":mission,"status":"blocked"})
        return self.reply(200, result)

def main():
    verify_modules()
    # Import the verified modules, without launching their HTTP servers.
    import inference_bridge_v051 as inference
    import review_bridge_v051 as review
    import patch_bridge_v051 as patch
    inference.interpreter()
    review.read_fixture()
    patch.read_fixture()
    if not QA_PYTHON.is_file() or not os.access(QA_PYTHON, os.X_OK):
        raise RuntimeError("CrewAI interpreter unavailable")
    secret = inference.secret()
    with Server(("127.0.0.1", PORT), Handler) as server:
        server.secret = secret
        server.missions = {
            "acp.initialize": initialize,
            "acp.inference": inference.probe,
            "acp.review_invoice_fixture": review.probe,
            "acp.patch_invoice_fixture": patch.probe,
            QA_MISSION: qa_probe,
        }
        print("HOST-011.4 MISSION_BRIDGE_READY: 127.0.0.1:18770 (v0.6.0)", flush=True)
        print("Fixed missions: 5 | Pinned modules: PASS | Serial execution", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit("Unsupported arguments")
    main()
