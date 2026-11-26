#!/usr/bin/env python3
"""HOST-010 ACP wire probe. No session, prompt, tools or inference."""
import json
import os
import selectors
import shutil
import subprocess
import sys
import time

def main():
    executable = shutil.which("hermes")
    if not executable:
        raise RuntimeError("Hermes executable unavailable")
    with subprocess.Popen([executable, "acp"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          start_new_session=True) as child:
        try:
            message = {"jsonrpc":"2.0", "id":1, "method":"initialize",
                       "params":{"protocolVersion":1, "clientCapabilities":{},
                                 "clientInfo":{"name":"zunpy-host010-probe","version":"0.1.0"}}}
            child.stdin.write((json.dumps(message)+"\n").encode())
            child.stdin.flush()
            deadline = time.monotonic()+25
            buf = b""
            with selectors.DefaultSelector() as sel:
                sel.register(child.stdout, selectors.EVENT_READ)
                while time.monotonic()<deadline:
                    if not sel.select(max(0,deadline-time.monotonic())):
                        break
                    chunk = os.read(child.stdout.fileno(), 8192)
                    if not chunk:
                        raise RuntimeError("ACP exited before initialization")
                    buf += chunk
                    if len(buf)>262144:
                        raise RuntimeError("Oversized ACP frame")
                    while b"\n" in buf:
                        line,buf=buf.split(b"\n",1)
                        if not line.strip():
                            continue
                        msg=json.loads(line)
                        if msg.get("method") and "id" in msg:
                            # Never approve any unsolicited request.
                            child.stdin.write((json.dumps({"jsonrpc":"2.0","id":msg["id"],
                                "error":{"code":-32601,"message":"Not permitted in probe"}})+"\n").encode())
                            child.stdin.flush()
                        if msg.get("id")==1 and "method" not in msg:
                            result=msg.get("result")
                            if not isinstance(result,dict) or result.get("protocolVersion")!=1:
                                raise RuntimeError("ACP protocol negotiation failed")
                            print("ACP_PROTOCOL_VERSION: 1")
                            print("ACP_INITIALIZE: PASS")
                            print("HOST-010.2 ACP_TRANSPORT: PASS")
                            return
            raise RuntimeError("ACP initialization timeout")
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
if __name__=="__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as exc:
        print("HOST-010.2 ACP_TRANSPORT: BLOCKED ("+type(exc).__name__+")",file=sys.stderr)
        sys.exit(1)
