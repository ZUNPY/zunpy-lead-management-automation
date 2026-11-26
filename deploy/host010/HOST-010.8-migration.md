# HOST-010.8 — Workflow migration and legacy retirement

Date: 2026-11-26.

Consolidated v0.5.1 passed regression 141 (four missions). Individual workflows migrated to `http://127.0.0.1:18770/mission` by updating only HTTP URL; readback verified all four destinations, fixed mission names, existing credential references, verifier presence, manual execution availability and timeouts. No new mission execution after migration; consolidated regression remains acceptance evidence.

| Workflow ID | Mission | Old port | New port | Migrated version |
|---|---|---|---|---|
|4aEh0uGOxxlVO4dK|acp.initialize|18766|18770|ceff03bb-d67c-4c3e-be9f-356ae01397ea|
|lZ7JC4IGb6qK9IjR|acp.inference|18767|18770|db7358b0-fc28-4bab-b889-5ac875dabad3|
|LTSznfmj9cZqBB6X|acp.review_invoice_fixture|18768|18770|df441b50-23df-4953-ab22-72dae8655b44|
|dD8SkU7mZwf1JN9Y|acp.patch_invoice_fixture|18769|18770|4fefea3d-205a-4af0-af99-32b72cc5210b|

Migration configuration: VERIFIED. Legacy process retirement: PENDING user confirmation. Stop only the four legacy bridge processes using Ctrl+C in their respective terminals. Retain the consolidated process on port 18770. Preserve all files, notably `host010-bridge/bridge-secret` and `host010-review/review_fixture.py`, which the consolidated modules still require. Do not stop Hermes or Ollama. No general shell access is available via this bridge.

Final optional listener check: `ss -ltn '( sport >= :18766 and sport <= :18770 )'` should show only the 18770 listener within this port range. This does not prove all host processes are stopped.
