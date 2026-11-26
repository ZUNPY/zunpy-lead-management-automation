# HOST-010 — Hermes bridge

## 2026-11-26 — Transport verified

Operator output confirms Hermes Agent v0.23.0 (local 2bd378ed1b8d), Python 3.14.9, installed under ~/.hermes/hermes-agent. ACP initialization over newline-delimited JSON-RPC negotiated protocol version 1 successfully. Probe commit 146aa9a8f940874c1b65fb394a9abc3337a3dcb9. No session prompt or inference in probe. No change to Hermes/Ollama/CrewAI configuration. JOB-005 candidate remains frozen on separate branch.

Next: inspect ACP permission/session behavior, design bounded mission runner, establish authenticated n8n-to-runner transport and test a synthetic mission. ACP initialization alone does not prove execution isolation or ChatGPT connectivity. Do not expose unrestricted shell access or rely on prompts as a security boundary. No automatic approval of sensitive actions. Production changes remain subject to explicit operator authorization.

## 2026-11-26 — Fixed mission bridge staged; n8n draft ready

Operator reports HOST-010.3 BRIDGE_STAGED: PASS and BRIDGE_READY on 127.0.0.1:18766 from installer commit 90cb33c561efc98fb3c6b85ca52d266103edacb7. Service runs in foreground, only accepts authenticated fixed acp.initialize mission, no inference or arbitrary command. Dedicated secret generated locally. HTTP authentication and end-to-end execution not yet verified. n8n draft workflow 4aEh0uGOxxlVO4dK created in personal project, version df640123-7e08-4d90-a358-0dea8f8b8769, manual trigger -> disabled private HTTP request -> exact response validator. Unpublished, no retries, 60 second execution limit. Next: operator creates separate Header Auth credential with header X-ZUNPY-Hermes-Auth and local host010-bridge/bridge-secret (never paste to chat); bind credential, enable HTTP node only for manual acceptance, validate end-to-end result. No Hermes/Ollama/CrewAI changes; no inference authorized in current probe.
