# HOST-010.4 / HOST-010.5

## HOST-010.4 — VERIFIED (2026-11-26)

- n8n workflow `4aEh0uGOxxlVO4dK`, manual execution `135`, status success.
- UTC start 20:31:33.126; end 20:31:34.537 (1.411 s).
- HTTP bridge and independent verification node both returned `{"mission":"acp.initialize","status":"verified","protocolVersion":1,"inference":false}`.
- Fixed authenticated localhost POST, no redirects, no caller-provided prompts or commands; bridge remains on 127.0.0.1:18766. Workflow unpublished. Authentication secret excluded from repository.
- Execution 134 failed before HTTP transport because the configured header name was invalid; corrected before 135.

## HOST-010.5 — PROPOSED, not verified

Objective: one fixed harmless reasoning prompt through a separate ACP session using the local Gemma 4 route. Return bounded text, stop reason, model identity evidence, no tool calls. Do not use inference alone as evidence of model identity. Preserve the existing bridge, credential and working probe.

Gate before sending a prompt: establish the effective model/provider and tool policy of the installed Hermes version. Default ACP toolsets may include terminal/code execution and permission requests are not a universal mediation layer. A fixed prompt and denying client requests are insufficient to guarantee no tools. Prefer an isolated session/profile with effective empty tool set, no MCP/plugins, local provider only and no fallback to external providers. Do not modify or restart the existing Hermes or Ollama services. If the installed release cannot enforce this policy, keep inference blocked until isolation is available. No general shell endpoint.

Acceptance: real n8n manual execution; ACP initialize, new session and prompt succeed; actual model/provider identified; bounded response returned; no tools offered or called; timeout enforced; old probe remains unchanged. No claims of acceptance until observed.

Reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/acp
