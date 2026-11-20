# Quote Follow-up V1

**Status:** E2E VERIFIED — SANDBOX  
**Component:** ZUNPY Lead Management Automation  
**Last verified:** 20 November 2026

## 1. Purpose

Quote Follow-up V1 automates the operational work that happens after a commercial quote has been sent.

Its goal is not to make commercial decisions. Its goal is to ensure that:

- due quotes are detected;
- a customer reply is checked before any automated follow-up;
- follow-up stages are sent in a deterministic sequence;
- duplicate sends are blocked;
- automation stops after the final stage;
- replies, terminal no-response cases and errors are handed to a human.

## 2. Workflow Chain

```text
QF-01 Quote Registration
        ↓
QF-02 Due Quote Orchestrator
        ↓
QF-03 Reply Guard
   ┌────┴───────────┐
REPLIED           NO_REPLY
   ↓                 ↓
QF-05 Human      QF-04 Follow-up
Review           Sender
                     ↓
                FU1 → FU2 → FU3
                             ↓
                        QF-05 Human
                           Review
```

## 3. QF-01 — Quote Registration

Responsibilities:

- normalize quote input;
- validate required data;
- reject duplicate quote IDs;
- create the CRM quote record;
- initialize the follow-up state;
- log the registration event.

QF-01 does not send follow-up emails.

## 4. QF-02 — Due Quote Orchestrator

Responsibilities:

- periodically read quote records;
- select only active and eligible quotes;
- require a valid due timestamp;
- hand each due quote to QF-03.

The sandbox workflow remains inactive unless a controlled test is explicitly run.

## 5. QF-03 — Reply Guard

QF-03 is the safety gate before every automated quote follow-up.

Responsibilities:

- read the Gmail conversation;
- establish the relevant outbound baseline;
- detect whether the customer has replied after that baseline;
- route **NO_REPLY** to QF-04;
- route **REPLIED** to QF-05;
- route Gmail-check failures to review.

A customer reply always stops the automated follow-up path.

## 6. QF-04 — Follow-up Sender

The current cadence is:

| Stage | Timing |
|---|---|
| FU1 | Day 3 |
| FU2 | Day 7 |
| FU3 | Day 14 |

After FU3:

- the quote becomes inactive;
- no next automated action is scheduled;
- there is no FU4;
- the case is handed to QF-05.

### Idempotency

Each follow-up stage uses a deterministic activity identifier derived from the quote and stage.

Before sending, the workflow checks whether that activity already exists.

If it exists, the send is blocked.

### Gmail implementation note

A thread-level reply operation was rejected during controlled testing.

The verified implementation uses the Gmail **message reply** operation and a known outbound message/thread reference.

This behavior is preserved as part of the validated implementation.

## 7. QF-05 — Human Review & Alerts

QF-05 is the terminal review layer for:

- **REPLIED**
- **NO_RESPONSE_AFTER_FU3**
- **ERROR**

Responsibilities:

- create a review record;
- prevent duplicate review creation;
- write an activity-log event;
- prepare an internal alert;
- leave the commercial decision to a human.

QF-05 does not make pricing, negotiation, acceptance or contract decisions.

## 8. CRM Records

The sandbox CRM separates operational data into four logical tables:

- **Quotes** — quote state and follow-up progression.
- **Activity_Log** — auditable workflow events.
- **Review_Queue** — cases requiring human action.
- **Error_Log** — workflow and integration failures.

No credentials or internal connection secrets are stored in this repository.

## 9. Verified End-to-End Scenario

A controlled internal test quote was initialized as:

- active;
- due;
- already at follow-up stage 2;
- connected to a controlled Gmail thread.

The E2E run produced the following sequence:

1. QF-02 detected the quote as due.
2. QF-03 read the real Gmail thread.
3. QF-03 found no customer reply after the outbound baseline.
4. QF-03 authorized QF-04.
5. QF-04 sent FU3 to the controlled internal recipient.
6. QF-04 logged the send.
7. QF-04 updated the quote to FOLLOWUP_3.
8. The quote was marked inactive with no future automatic action.
9. QF-04 handed the terminal case to QF-05.
10. QF-05 created an OPEN human-review item.
11. QF-05 logged HUMAN_REVIEW_CREATED.

All four workflow executions completed successfully.

## 10. Additional Verified Behaviors

The sandbox also verified independently that:

- a real FU1 could be delivered through Gmail;
- a repeated FU1 attempt was blocked as a duplicate;
- a real internal QF-05 alert could be delivered;
- repeating the same review event did not create or send a duplicate alert;
- a real customer reply path was detected and blocked from follow-up;
- Gmail integration failures route to review instead of silently continuing.

## 11. Safety Invariants

The subsystem follows these invariants:

1. **Fail closed.**
2. Never send follow-up unless QF-03 returns NO_REPLY.
3. A detected customer reply cancels automated follow-up.
4. Never send the same follow-up stage twice.
5. Never generate an automatic FU4.
6. After FU3, require human review.
7. Log integration failures.
8. Keep commercial decisions human-controlled.
9. Do not enable production sending as part of sandbox testing.
10. Do not expose OAuth secrets, API keys or internal credentials in public documentation.

## 12. Current Sandbox State

The validated sandbox configuration is deliberately safe:

- workflows are inactive;
- real client sending is disabled;
- internal alerts are disabled by default;
- test data is fictional or controlled internal data.

## 13. Production Boundary

E2E verification demonstrates that the architecture and workflow logic work in the tested sandbox conditions.

It does **not** claim universal production readiness.

A real deployment still requires:

- client-specific requirements;
- production credentials;
- acceptance testing;
- recipient and domain policy review;
- monitoring and operational ownership;
- agreed error handling and escalation;
- any required privacy or regulatory controls.

---

**Result:** Quote Follow-up V1 is a verified sandbox subsystem suitable for demonstration, portfolio evidence and controlled client adaptation.
