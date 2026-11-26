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

## Integrated sandbox acceptance — 2026-11-26

- Backend candidate: `23288088e79f0315611b74d92f7c86ae2ee69043`.
- Operator-reported terminal acceptance: **28/28 tests PASS in 3.004 s**; includes actual disposable PostgreSQL, ASGI public recovery routes with explicitly overridden sandbox delivery dependency, temporary Unix socket relay, and live synthetic n8n webhook. No actual PayPal payment or email.
- Checkout retries no longer rotate existing order credentials or extend deadlines. Three lifecycle tests passed, including pending link preservation and post-redemption retries. Expired and partially provisioned orders require reconciliation rather than automatic reactivation.
- Website candidate branch `website-job005-recovery`, commit `4f160a6c63d07b35b15e21a08c3928addee828e1`: three simulated browser contract scenarios passed (paid retry, explicit fragment redemption, recovery request). Real browser acceptance remains pending.
- n8n workflow version `abb0dca6-abfe-465b-8460-5b8699d43d32` accepted synthetic expiring link payload; Gmail remained disabled. Workflow unpublished via MCP after acceptance.

Sandbox integration is verified; **production recovery is not enabled**. No deployment or migration of active services performed. Remaining release gates: full candidate build/start, permanent least-privilege relay, actual proxy identity and input privacy, approved real delivery and failure handling, reconciliation for partial orders, real browser and deployment acceptance. The earlier remaining gate for checkout retry safety is superseded by the successful tests above.

## Persistent sandbox relay — 2026-11-26

Installer commit `79162961842c5e260942bc6cd68d71fadcae8ee1`. Operator reported PERSISTENT_SANDBOX_RELAY: INSTALLED, PERSISTENT_RELAY_RESTART: PASS, JOB-005.2.20 PERSISTENT_RELAY: PASS. Dedicated non-root nginx container, host-network upstream to loopback n8n, private Unix socket directory, no new TCP listener configured, explicit synthetic webhook route and restart policy. The probe passed from an isolated container with the host user's UID/GID after relay restart. No active API or production configuration changed. Sandbox workflow unpublished via MCP again. Host reboot survival and final active API UID/mount permissions are not yet verified.

## Candidate startup acceptance — 2026-11-26

Candidate `c037935741a15c4dddc179e21422e8083f52b09f`. Operator reported all five gates PASS: candidate image build (11.1 s), missing-schema startup rejected, additive migration run twice plus check-only, candidate Uvicorn boot with both public recovery endpoints returning 503/no-store, and previous image startup on migrated disposable PostgreSQL. The candidate was built atop existing local image `zunpy-jobs-api:125fe13`; not a clean dependency rebuild. No active database migration or deployment performed. This verifies previous image startup compatibility, not every possible data rollback scenario. Public recovery remains disabled. Next release gates: proxy/source identity and input privacy, actual approved mail delivery, real browser acceptance and deployment authorization.

## Recovery HTTP privacy — 2026-11-26

Candidate `4267864d7875c1e2cf096a3873f20fd0511030bd`: operator reported three targeted tests PASS in 0.065 s. Credential-bearing routes now return generic no-store 422 responses for invalid input; candidate startup explicitly disables Uvicorn proxy headers. Direct ASGI peer quota identity resisted forged forwarded headers in the test, including IPv4-mapped IPv6 and IPv6 /64 normalization. Public recovery still fails closed. Total cumulative backend acceptance: 28 earlier integration tests plus 3 targeted tests (not yet a single 31-test regression at this commit). Actual trusted edge/client identity, edge request size limits, real approved delivery, failure handling and browser acceptance remain release gates. No live configuration changed.

## Authorized mail acceptance — 2026-11-26

One explicitly authorized test email to the business inbox, using a separate unpublished manual-only n8n workflow in the personal project. Execution 127 succeeded at 18:49:40 UTC. Gmail connector independently verified receipt at 18:49:39 UTC, INBOX label, exact subject "ZUNPY — Recovery Sandbox Test". Message contained an intentionally nonfunctional illustrative link, no valid credentials or customer data. One-time workflow archived immediately after the successful execution. This verifies the Gmail transport and receipt, not delivery of a live recovery credential or browser redemption. Main recovery workflow remains unpublished and its mail node disabled. No production activation.

## Real browser recovery — 2026-11-26

Operator reported JOB-005.2.24 REAL_BROWSER_RECOVERY: PASS at backend candidate 8f3fb6ce157401c7becde68ca6306670379bbac8 and website 4f160a6c63d07b35b15e21a08c3928addee828e1. Initial harness failed to generate a link; revised harness uses explicit disposable database dependency and separate HTTP delivery preflight. Preflight 202 and delivery PASS, browser request accepted, local link generated, explicit Restore access displayed Access restored, real order status returned 200, original access hash invalidated, recovery row consumed and replay rejected with HTTP 400. Harness changes only the website API origin and uses a local delivery callback, not live mail or production ingress. Temporary PostgreSQL and API containers cleaned on normal exit. No production deployment. Do not retain raw test link. Remaining release gates include combined regression of backend candidate, trusted ingress identity and body limits, production delivery configuration and failure/reconciliation policy. Mail acceptance was separate self-delivery, not an external mailbox or complete production recovery flow.

## Full backend regression — 2026-11-26

Operator reported JOB-005.2.25 FULL_REGRESSION: PASS at d1edbdae8ce475f7b40728ab1cf9016617cdda7b. All 31 tests passed together in 2.960 seconds, zero skips or failures. Disposable PostgreSQL, installed base image dependencies, candidate modules, synthetic n8n delivery through persistent private Unix relay; payment provider mocks, recovery concurrency, quota, privacy, checkout retry and redemption covered. No actual payment or mail during regression. Sandbox workflow version abb0dca6-abfe-465b-8460-5b8699d43d32 was temporarily published with Gmail disabled and unpublished after acceptance. This is a sandbox regression checkpoint, not approval to expose the public recovery service. Production delivery, trusted ingress, request size controls and reconciliation remain open. No production migration or deployment.

## Candidate recovery mail adapter — 2026-11-26

Operator reported JOB-005.2.26 MAIL_ADAPTER: PASS at 6041a71ac581550028b6005a6566eff26b6171c9: five isolated unit tests passed in 0.021 seconds. Single ASCII dot-atom recipient, order identifier, token, expiry and secret validation; private Unix HTTP transport contract; exact HTTP 200 JSON acknowledgement; ambiguous failures redacted without retry. Mock transport only. Combined cumulative backend evidence is 31 previously regressed tests plus 5 targeted tests, not a single 36-test regression. Production mail workflow, separate private relay route, delivery acknowledgement integration, operational failure policy and public activation are still pending. No mail sent or production changes.
