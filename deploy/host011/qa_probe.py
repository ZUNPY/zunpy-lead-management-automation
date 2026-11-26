#!/usr/bin/env python3
"""HOST-011.3: fixed CrewAI QA probe, no external tools or delegation."""
import os
import sys
import re
import json
import tempfile
import subprocess
from pathlib import Path

MODEL = "gemma4:26b"
ENDPOINT = "http://127.0.0.1:11434/v1"

def worker():
    # Defense in depth, not OS sandboxing.
    def guard(event, args):
        if event == "socket.connect":
            address = args[1]
            if not (isinstance(address, tuple) and address[:2] == ("127.0.0.1", 11434)):
                raise PermissionError("Non-Ollama connection denied")
        elif event == "socket.getaddrinfo":
            if args[0] != "127.0.0.1" or str(args[1]) != "11434":
                raise PermissionError("Non-Ollama resolution denied")
    sys.addaudithook(guard)
    import crewai
    from crewai import Agent, Crew, Task, Process, LLM
    if crewai.__version__ != "1.15.28":
        raise RuntimeError("Unexpected CrewAI version")
    llm = LLM(model="openai/" + MODEL, base_url=ENDPOINT, api_key="ollama",
              temperature=0, max_tokens=1024, timeout=90)
    reviewer = Agent(
        role="Independent software QA reviewer",
        goal="Evaluate invoice calculations against the stated requirements, not prior agent conclusions.",
        backstory="You review small Python changes independently and report precise defects.",
        llm=llm, tools=[], allow_delegation=False, allow_code_execution=False,
        max_iter=2, max_retry_limit=0, verbose=False)
    task = Task(
        description="""Requirement: invoice_total must add the tax to the subtotal and round to two decimals.
Review these two candidate implementations independently. Do not execute or modify anything.
Candidate A:
def invoice_total(subtotal, tax_rate):
    tax = subtotal * tax_rate
    return round(subtotal - tax, 2)
Candidate B:
def invoice_total(subtotal, tax_rate):
    tax = subtotal * tax_rate
    return round(subtotal + tax, 2)
For subtotal 100 and tax rate 0.21, calculate the result of each candidate.
Report exactly three plain-text lines: A: ACCEPT or REJECT followed by the numeric result; B: ACCEPT or REJECT followed by the numeric result; REASON: one concise explanation.
Example format only: A: ACCEPT 123; use a newline instead of a semicolon before B.""",
        expected_output="Three lines: A: <verdict> <number>, B: <verdict> <number>, REASON: <explanation>.",
        agent=reviewer, tools=[])
    crew = Crew(agents=[reviewer], tasks=[task], process=Process.sequential,
                memory=False, planning=False, verbose=False)
    result = crew.kickoff()
    answer = result.raw.strip()
    if answer.startswith("```") and answer.endswith("```"):
        answer = "\n".join(answer.splitlines()[1:-1]).strip()
    match = re.fullmatch(r"A:\s*(ACCEPT|REJECT)\s+(\d+(?:\.\d+)?)\s*\nB:\s*(ACCEPT|REJECT)\s+(\d+(?:\.\d+)?)\s*\nREASON:\s*([^\r\n]{1,400})", answer, re.IGNORECASE)
    if not match:
        print("QA_OUTPUT_FORMAT_BLOCKED", flush=True)
        raise RuntimeError("Unexpected QA output format")
    if (match[1].upper(), float(match[2]), match[3].upper(), float(match[4])) != ("REJECT",79.0,"ACCEPT",121.0):
        raise RuntimeError("QA verdict or calculation incorrect")
    print("HOST-011.3 QA_PASS:", json.dumps({
        "crewaiVersion":crewai.__version__, "modelConfigured":MODEL, "endpoint":ENDPOINT,
        "original":{"verdict":match[1].upper(),"actual":float(match[2])},
        "patched":{"verdict":match[3].upper(),"actual":float(match[4])},
        "reason":match[5].strip(), "toolsConfigured":0
    }), flush=True)

def main():
    with tempfile.TemporaryDirectory(prefix="zunpy-crewai-qa-") as temp:
        home = Path(temp)
        env = {"HOME":str(home), "PATH":str(Path(sys.executable).parent)+":/usr/bin:/bin",
               "LANG":"C.UTF-8", "PYTHONNOUSERSITE":"1", "PYTHONDONTWRITEBYTECODE":"1",
               "OTEL_SDK_DISABLED":"true", "CREWAI_DISABLE_TELEMETRY":"true",
               "NO_PROXY":"*", "XDG_CONFIG_HOME":str(home/".config"),
               "XDG_CACHE_HOME":str(home/".cache"), "XDG_DATA_HOME":str(home/".local/share")}
        result = subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"--worker"],
                                cwd=home, env=env, timeout=150, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

if __name__ == "__main__":
    if sys.argv[1:] == ["--worker"]:
        worker()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit("Unsupported arguments")
