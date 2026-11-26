#!/usr/bin/env python3
"""HOST-010.5 candidate: separate fixed-prompt ACP bridge. No arbitrary input."""
import asyncio
import hmac
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL = "gemma4:26b"
ENDPOINT = "http://127.0.0.1:11434/v1"
MISSION = "acp.inference"
PROMPT = "Calculate 17 + 25. Reply with only the decimal number, without punctuation or explanation."
ROOT = Path.home() / "proyectos/zunpy-host"
HERMES = Path.home() / ".hermes/hermes-agent"
PORT = 18767
DEADLINE = 165

def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def worker():
    # Keep a dedicated pipe for ACP JSON-RPC, before importing Hermes.
    # All ordinary Python and fd-1 diagnostics now go to stderr, never ACP.
    sys.stdout.flush()
    wire = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    # Launched in a fresh process with an ephemeral home and minimal environment.
    # This audit guard is defense in depth, not an OS sandbox.
    def guard(event, args):
        if event == "socket.connect":
            address = args[1]
            if not (isinstance(address, tuple) and address[:2] == ("127.0.0.1", 11434)):
                raise PermissionError("Non-Ollama connection denied")
        elif event == "socket.getaddrinfo":
            if args[0] != "127.0.0.1" or str(args[1]) != "11434":
                raise PermissionError("Non-Ollama name resolution denied")
        elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"):
            raise PermissionError("Child process denied")
    sys.addaudithook(guard)
    import acp
    from acp_adapter.server import HermesACPAgent
    from acp_adapter.session import SessionManager
    from run_agent import AIAgent

    def factory():
        agent = AIAgent(model=MODEL, provider="custom", api_mode="chat_completions",
                        base_url=ENDPOINT, api_key="ollama",
                        enabled_toolsets=[], quiet_mode=True, platform="acp",
                        skip_context_files=True, skip_memory=True,
                        skip_background_review=True, load_soul_identity=False,
                        fallback_model={}, max_iterations=1, max_tokens=128)
        require(agent.model == MODEL, "model mismatch")
        require(str(agent.base_url).rstrip("/") == ENDPOINT, "endpoint mismatch")
        require(agent.enabled_toolsets == [] and not agent.tools and not agent.valid_tool_names,
                "nonempty tool surface")
        return agent

    class RestrictedACP(HermesACPAgent):
        async def _register_session_mcp_servers(self, state, mcp_servers):
            require(not mcp_servers, "MCP denied")

        def _schedule_mcp_late_refresh(self, state):
            return None

        async def prompt(self, prompt, session_id, **kwargs):
            state = self.session_manager.get_session(session_id)
            require(state is not None and state.agent.model == MODEL, "session mismatch")
            require(state.agent.enabled_toolsets == [] and not state.agent.tools
                    and not state.agent.valid_tool_names, "tool surface changed")
            require(len(prompt) == 1 and getattr(prompt[0], "text", None) == PROMPT,
                    "prompt denied")
            return await super().prompt(prompt, session_id, **kwargs)

    server = RestrictedACP(session_manager=SessionManager(agent_factory=factory))
    async def serve():
        try:
            # SDK 0.9.0: use explicit asyncio writer/reader streams.
            from acp.stdio import _WritePipeProtocol
            loop = asyncio.get_running_loop()
            reader = asyncio.StreamReader(limit=262144)
            await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
            protocol = _WritePipeProtocol()
            transport, _ = await loop.connect_write_pipe(lambda: protocol, wire)
            writer = asyncio.StreamWriter(transport, protocol, None, loop)
            await acp.run_agent(server, input_stream=writer, output_stream=reader,
                                use_unstable_protocol=True)
        finally:
            await server.aclose()
    asyncio.run(serve())

def interpreter():
    for path in (HERMES / ".venv/bin/python", HERMES / "venv/bin/python"):
        if path.is_file() and os.access(path, os.X_OK):
            return path
    raise RuntimeError("Hermes venv Python not found")

def probe():
    python = interpreter()
    # JSON is valid YAML; never copy the user's real config or .env.
    with tempfile.TemporaryDirectory(prefix="zunpy-inference-") as folder:
        home = Path(folder)
        profile = home / ".hermes"
        profile.mkdir(mode=0o700)
        (profile / "config.yaml").write_text(json.dumps({
            "model": {"default": MODEL, "provider": "custom", "base_url": ENDPOINT},
            "platform_toolsets": {"acp": ["no_mcp"]},
            "mcp_servers": {}, "fallback_models": [], "plugins": {},
            "agent": {"disabled_toolsets": [], "reasoning_effort": "none"}
        }), encoding="utf-8")
        env = {"HOME": str(home), "HERMES_HOME": str(profile),
               "PATH": str(python.parent) + ":/usr/bin:/bin",
               "PYTHONPATH": str(HERMES), "PYTHONNOUSERSITE": "1",
               "PYTHONUNBUFFERED": "1", "LANG": "C.UTF-8",
               "NO_PROXY": "*", "XDG_CONFIG_HOME": str(home / ".config"),
               "XDG_CACHE_HOME": str(home / ".cache")}
        child = subprocess.Popen([str(python), str(Path(__file__).resolve()), "--worker"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, cwd=home, env=env,
                                 start_new_session=True)
        stop = time.monotonic() + DEADLINE
        buffer = b""
        parts = []
        session = None
        def send(obj):
            child.stdin.write((json.dumps(obj) + "\n").encode())
            child.stdin.flush()
        def call(sel, ident, method, params):
            nonlocal buffer
            send({"jsonrpc":"2.0","id":ident,"method":method,"params":params})
            while time.monotonic() < stop:
                if not sel.select(max(0, stop-time.monotonic())):
                    break
                chunk = os.read(child.stdout.fileno(), 8192)
                require(chunk, "ACP exited")
                buffer += chunk
                require(len(buffer) <= 262144, "ACP frame too large")
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except (UnicodeError, json.JSONDecodeError) as exc:
                        raise RuntimeError("ACP wire frame is not JSON") from exc
                    require(isinstance(msg, dict), "ACP wire frame is not an object")
                    if "method" in msg:
                        if "id" in msg:
                            send({"jsonrpc":"2.0","id":msg["id"],"error":{
                                "code":-32601,"message":"Not permitted"}})
                            raise RuntimeError("ACP tool or permission request denied")
                        if msg["method"] == "session/update":
                            p = msg.get("params", {})
                            u = p.get("update", {})
                            kind = u.get("sessionUpdate", "")
                            require(kind not in ("tool_call", "tool_call_update"), "tool event denied")
                            if kind == "agent_message_chunk" and p.get("sessionId") == session:
                                content = u.get("content", {})
                                if content.get("type") == "text":
                                    parts.append(content.get("text", ""))
                                    require(sum(len(x) for x in parts) <= 2048, "output too long")
                    elif msg.get("id") == ident:
                        require("error" not in msg and isinstance(msg.get("result"), dict),
                                "ACP request failed")
                        return msg["result"]
            raise RuntimeError("ACP timeout")
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(child.stdout, selectors.EVENT_READ)
                init = call(sel, 1, "initialize", {"protocolVersion":1,"clientCapabilities":{},
                    "clientInfo":{"name":"zunpy-inference","version":"0.2.0"}})
                require(init.get("protocolVersion") == 1, "ACP version mismatch")
                new = call(sel, 2, "session/new", {"cwd":str(home),"mcpServers":[]})
                session = new.get("sessionId")
                require(isinstance(session,str) and session, "missing session")
                result = call(sel, 3, "session/prompt", {"sessionId":session,
                    "prompt":[{"type":"text","text":PROMPT}]})
                answer = "".join(parts).strip()
                require(result.get("stopReason") == "end_turn" and answer == "42", "unexpected inference result")
                return {"mission":MISSION,"status":"verified","protocolVersion":1,
                        "inference":True,"modelConfigured":MODEL,
                        "endpoint":ENDPOINT,"answer":answer,"toolEvents":0}
        finally:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

def secret():
    p = ROOT / "host010-bridge/bridge-secret"
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600, "credential mode")
        raw = f.read(66)
    require(re.fullmatch(rb"[0-9a-f]{64}\n?", raw), "credential format")
    return raw.strip()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def reply(self, status, data):
        b = json.dumps(data, separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.send_header("Cache-Control","no-store")
        self.send_header("Connection","close")
        self.end_headers()
        self.wfile.write(b)
        self.close_connection = True
    def do_POST(self):
        self.connection.settimeout(5)
        keys = self.headers.get_all("X-ZUNPY-Hermes-Auth", [])
        if self.path != "/mission":
            return self.reply(404, {"status":"not_found"})
        if len(keys) != 1 or not hmac.compare_digest(keys[0].encode(), self.server.secret):
            return self.reply(403, {"status":"denied"})
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,3}",lengths[0]):
            return self.reply(400, {"status":"invalid_request"})
        n = int(lengths[0])
        if not 1 <= n <= 256:
            return self.reply(400, {"status":"invalid_request"})
        try:
            body = self.rfile.read(n)
            require(len(body) == n and json.loads(body) == {"mission":MISSION}, "invalid mission")
        except (ValueError, OSError, RuntimeError):
            return self.reply(400, {"status":"invalid_mission"})
        try:
            self.connection.settimeout(200)
            result = probe()
        except Exception as exc:
            # Local terminal receives a bounded class name only, no secrets or prompt traces.
            print("HOST-010.5 BLOCKED:", type(exc).__name__, flush=True)
            return self.reply(503, {"mission":MISSION,"status":"blocked"})
        return self.reply(200,result)

if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        worker()
    elif not sys.argv[1:]:
        interpreter()
        with HTTPServer(("127.0.0.1",PORT),Handler) as server:
            server.secret = secret()
            print("HOST-010.5 INFERENCE_BRIDGE_READY: 127.0.0.1:18767", flush=True)
            server.serve_forever()
    else:
        raise SystemExit("Unsupported arguments")
