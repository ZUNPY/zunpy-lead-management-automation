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

## Candidate recovery mail workflow — 2026-11-26

Created unpublished n8n workflow i9WaautJTLqkCusz, version 3790cec0-aea8-4cfc-8c3c-acda539f750d, personal project. Four nodes: authenticated loopback-only POST webhook /webhook/zunpy-job005-recovery-mail, strict four-field validation and bilingual plain text composition, Gmail disabled (existing business credential, no retry), acceptance check requiring provider id and threadId before exact {"status":"accepted"}. SDK validation passed and update reported no warnings. Synthetic manual test 129 reached acceptance gate and failed as intended with Gmail disabled; test 130 rejected a multiple-recipient string. Both expected errors, no mail sent. Execution lookup subsequently returned not found, consistent with disabled retention settings but not proof of comprehensive secret deletion. Existing sandbox header credential was autoassigned by n8n; NOT approved for production. Dedicated header credential and separate private relay must be provisioned before publishing; positive provider acknowledgement not yet tested on this workflow. Public API remains disabled; no production changes.

## Dedicated mail relay — 2026-11-26

Operator reported JOB-005.2.28 MAIL_RELAY_INSTALLED: PASS at 9ec24232fa3d6e2b910f5a68d23264717993d434. Separate container zunpy-recovery-mail-relay, private Unix socket recovery-mail-relay/socket/mail.sock, dedicated locally generated 256-bit header secret recovery-mail-relay/header-secret (0600). Isolation checks passed for sandbox path, wrong method and unpublished mail webhook. Existing sandbox relay unchanged. Production mail workflow remains unpublished; dedicated n8n header credential must be created and assigned, and authenticated delivery tested before activation. No actual mail sent.

## Dedicated authenticated mail channel — 2026-11-26

Operator reported JOB-005.2.30 PRIVATE_MAIL_CHANNEL: PASS. Dedicated Header Auth credential assigned to candidate workflow version 51a1d839-bee3-434b-a232-4dfe4ff77091. Via separate private Unix socket, missing authentication and sandbox credential rejected (401/403); dedicated credential reached the invalid-payload rejection path (HTTP 500 expected for this negative test). Gmail remained disabled throughout; candidate workflow unpublished after test. No real mail sent. Positive provider acknowledgement through the complete adapter/relay/workflow chain still requires controlled acceptance. No public API activation or production migration.

## End-to-end authorized recovery mail transport — 2026-11-26

Operator reported JOB-005.2.31 MAIL_E2E: PASS and PROVIDER_ACK: PASS. The dedicated Python mail adapter traversed the private Unix relay, dedicated header authentication, n8n and actual Gmail. Temporary workflow version 6a58c96a-be5e-4afc-82f7-9042f923171a restricted recipient, fictional order and synthetic token, with a 45-minute cutoff; local attempt marker prevents accidental repeat. Gmail independently confirmed exactly one matching message in the business inbox (19:20:56 UTC, subject ZUNPY — JOB-005.2.31 Recovery Mail E2E TEST). Workflow unpublished and previous disabled draft restored as d32ff5a5-4950-492b-89ae-7485307a5a87; readback confirms inactive and Gmail disabled. No real order, customer data or valid production token. This verifies transport and provider acceptance, not live delivery of a valid recovery link or delivery to external mailboxes. Production recovery configuration remains disabled. Pending gates: trusted public ingress, bounded requests, incomplete paid order reconciliation, operational handling of delivery failures and approved deployment.

## Recovery request body limits — 2026-11-26

Operator reported JOB-005.2.32 BODY_LIMIT: PASS at 3b9627accd71286d003d80549bb59d3b14f611f4. Five targeted ASGI tests passed in 0.021 seconds. Recovery public/private routes enforce 4096 bytes before parsing or database dependencies; declared and streamed oversize rejected, invalid or mismatched lengths rejected, valid JSON at the exact limit reaches disabled service. PDF upload and PayPal webhook remain outside this recovery-specific limit. Cumulative backend evidence: 31 jointly regressed tests plus 10 subsequent targeted tests, not a single 41-test run. Actual public ingress identity, ingress time/body controls, paid-order reconciliation and authorized activation remain pending. No production changes.

## Atomic checkout persistence — 2026-11-26

Operator inspected the installed baseline service functions: create_order and transition_order each commit independently. Candidate 87e68d77f11a0f5d543e15a330b3cb67c86a17d0 replaces these two commits in the PayPal route with a single transaction containing the WAITING_UPLOAD order and both audit events. Operator reported JOB-005.2.33 ATOMIC_CHECKOUT: PASS, 3 tests in 0.047s on disposable SQLite with mocked PayPal: injected interruption rolls back all rows/events, retry creates one order without rotating or returning an existing token, legacy PAID remains blocked. No real payment or production change. Existing incomplete payments still require operator reconciliation; concurrency on PostgreSQL and complete regression remain pending. Cumulative evidence: 31 previous joint regression tests plus 13 subsequent targeted tests, not a single 44-test run.

## Recovery assembly — 2026-11-26

Operator reported JOB-005.2.34 RECOVERY_ASSEMBLY: PASS at d8afb2cb2ddca1f90bd1adae1c0b471916298cad. Five targeted tests passed in 2.521s using synthetic secrets and a disposable Unix socket HTTP server. Explicit configuration requires separate 256-bit secrets in private regular files, rejects unsafe file modes and final symlinks, requires an absolute socket path, and connects the validated mail adapter. Negative acknowledgement logs generic failure without retry. Default public dependency still returns None even when environment flags are present. No real email sent or production changes. Cumulative evidence: 31 earlier joint regression tests plus 18 subsequent targeted tests, not yet a single 49-test run. Remaining: complete regression with PostgreSQL and synthetic n8n relay, verified ingress identity, actual deployment composition and explicit activation.
