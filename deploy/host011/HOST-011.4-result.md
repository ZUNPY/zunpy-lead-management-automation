# HOST-011.4 — Remote CrewAI QA acceptance

Date: 2026-11-26. Status: VERIFIED for fixed remote QA mission. Regression of four prior missions pending.

- Bridge candidate v0.6.0: commit `2f4287f2541dd0d652f34799c287cd8a3a3bbf41`; user terminal confirmed startup on 127.0.0.1:18770 with five pinned missions and serial execution. Frozen v0.5.1 retained.
- n8n workflow `glutcyin4Fz5qvvs`, ZUNPY — HOST-011.4 — CrewAI QA, manual, inactive, availableInMCP, authenticated existing header credential, no retries, execution timeout 200s.
- Execution `142`: directly launched and retrieved via n8n MCP by ChatGPT. Status success; started 2026-11-26T21:03:14.388Z, stopped 2026-11-26T21:03:18.208Z; elapsed 3.820s. Last node Verify CrewAI QA.
- Output: `{"mission":"crewai.qa_invoice_fixture","status":"verified","qaSchemaVersion":1,"crewaiVersion":"1.15.28","modelConfigured":"gemma4:26b","endpoint":"http://127.0.0.1:11434/v1","original":{"verdict":"REJECT","actual":79},"patched":{"verdict":"ACCEPT","actual":121},"reason":"Candidate A subtracts the tax instead of adding it.","toolsConfigured":0,"acceptance":"PASS"}`.

Scope: fixed QA fixture only; no arbitrary project access, no independent model identity attestation, no direct Hermes-to-CrewAI delegation. Both reviewers use the same configured underlying model. No manual terminal action was required for this remote execution after bridge deployment. Next: regression of prior four missions on v0.6.0 and coordinated engineering/QA workflow. Claude Code deferred by user.
