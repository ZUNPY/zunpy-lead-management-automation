# JOB-005.2 — Recovery sandbox checkpoint

Date: 2026-11-26. Status: sandbox verified in parts; NOT released.

## Evidence

- Candidate `3d1348cb4e59ca086eef6f289c361c2bf1aa3849`: 24/24 tests passed in the isolated PostgreSQL/Docker acceptance run reported by the operator (2.581 s).
- Explicit additive schema migration: both recovery tables, repeat execution, check-only startup guard, compatibility with the previous bootstrap verified on disposable databases.
- n8n: synthetic fixture accepted (execution 119), non-sandbox fixture rejected (120). Mail node disabled. Retention settings configured not to save execution data; this does not independently prove absence of secrets in all runtime storage.
- Local HTTP webhook: unauthenticated request rejected (403); authenticated request accepted (200).
- Temporary Python container host-network transport: `PYTHON_N8N_BRIDGE: PASS`.
- Candidate `7e3315e563319b4c42c3708c4befac2cfacb5a7d`: temporary Unix socket relay and Python container without IP networking: `PRIVATE_SOCKET_BRIDGE: PASS` reported by operator.
- Sandbox workflow unpublished again after the temporary activation via MCP. No real mail sent in these tests.

## Remaining gates

- Finalize capture retry and recovery credential lifecycle, including row locking, expiry preservation and protection against stale claim rotation.
- Verify reliable client identity at the actual proxy, including untrusted forwarded headers; enforce request limits before production exposure.
- Implement real delivery adapter and approved mail workflow, with explicit delivery failure handling and no raw credentials in logs or persisted execution history. Verify with synthetic data first.
- Provide recovery UI and a way for the customer to retain the order identifier; fragment-based link and explicit POST redemption.
- Integrate the permanent private transport with least-privilege permissions; temporary relay test does not prove persistent deployment.
- Validate complete candidate build/start, migration, rollback compatibility and end-to-end flow in isolation before approval of any live deployment.

No production migration, merge, customer contact or commercial activation authorized by this checkpoint.
