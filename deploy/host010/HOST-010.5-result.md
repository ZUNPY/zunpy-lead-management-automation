# HOST-010.5 — Fixed inference probe

Date: 2026-11-26.

Status: VERIFIED for the fixed end-to-end ACP inference probe. Independent backend model identity verification and full OS isolation are not established.

- Bridge candidate commit: `f37ae52e39a4d246f9d3a8c703cbe49bc86b8a02`.
- User reported bridge ready at `127.0.0.1:18767`.
- Separate unpublished n8n workflow: `lZ7JC4IGb6qK9IjR`.
- Manual execution: `136`, success, 20:38:08.098–20:38:35.586 UTC (27.488 seconds).
- Both HTTP and independent n8n verification nodes succeeded.
- Returned payload: `{"mission":"acp.inference","status":"verified","protocolVersion":1,"inference":true,"modelConfigured":"gemma4:26b","endpoint":"http://127.0.0.1:11434/v1","answer":"42","toolEvents":0}`.
- Fixed prompt arithmetic 17+25, expected result 42.
- Existing HOST-010.4 bridge and workflow left unchanged. No Hermes/Ollama service modifications.

Limitations: model identifier is configured and checked in the agent, not independently attested by backend telemetry. Zero ACP tool events are not proof of OS-level sandboxing. The temporary profile and Python audit restrictions are defense in depth, not a complete OS sandbox. No arbitrary prompts, shell access or file editing accepted. Next milestone: bounded read-only engineering mission within a dedicated workspace, with explicit permission and validation boundaries.
