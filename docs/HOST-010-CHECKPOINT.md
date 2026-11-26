# HOST-010 — Hermes bridge

## 2026-11-26 — Transport verified

Operator output confirms Hermes Agent v0.23.0 (local 2bd378ed1b8d), Python 3.14.9, installed under ~/.hermes/hermes-agent. ACP initialization over newline-delimited JSON-RPC negotiated protocol version 1 successfully. Probe commit 146aa9a8f940874c1b65fb394a9abc3337a3dcb9. No session prompt or inference in probe. No change to Hermes/Ollama/CrewAI configuration. JOB-005 candidate remains frozen on separate branch.

Next: inspect ACP permission/session behavior, design bounded mission runner, establish authenticated n8n-to-runner transport and test a synthetic mission. ACP initialization alone does not prove execution isolation or ChatGPT connectivity. Do not expose unrestricted shell access or rely on prompts as a security boundary. No automatic approval of sensitive actions. Production changes remain subject to explicit operator authorization.
