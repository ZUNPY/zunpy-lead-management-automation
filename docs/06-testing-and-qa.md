# ZUNPY Lead Management Automation
## Document 06 — Testing and QA

**Version:** 1.2  
**Status:** Test plan defined; execution and verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose

This document defines the testing strategy and acceptance tests for ZUNPY Lead Management Automation.

The objective is to verify that lead registration, validation, duplicate detection, CRM operations, notifications, follow-up management, error handling, and reporting behave according to the project requirements.

All tests must use synthetic data. No real customer or personal information shall be used during development and testing.

## 2. Testing Scope

The test plan covers:

- Automated lead registration.
- Manual lead registration.
- Webhook and REST API input.
- Data validation and normalization.
- Duplicate detection and conflict management.
- Centralized CRM operations.
- Activity and error logging.
- Owner notifications and lead acknowledgements.
- Follow-up creation, rescheduling, completion, and cancellation.
- Follow-up notification controls and failure scenarios.
- Timezone handling.
- Concurrency and data integrity.
- Basic reporting.
- Security and configuration checks.

## 3. Test Environment

The planned test environment shall include:

- n8n.
- Google Sheets with the four project worksheets.
- Gmail integration.
- Public and internal n8n forms.
- Webhook endpoint.
- REST API test requests.
- Synthetic lead data.
- Configured local timezone: `Europe/Madrid`.

The test environment shall use the same workflow structure and relevant configuration intended for deployment.

All credentials must be configured through the appropriate n8n credential mechanisms.

Testing shall cover Gmail and other configured integrations. Ollama is not a required component of this project.

## 4. Test Data

Synthetic test data shall include:

- Valid names and email addresses.
- Valid phone numbers.
- Invalid email addresses.
- Missing contact information.
- Existing lead records.
- Duplicate email matches.
- Duplicate phone matches.
- Conflicting email and phone matches.
- Leads with different statuses.
- Pending, completed, and cancelled follow-ups.
- Simulated integration and workflow failures.

Each test execution shall use identifiable test records to make results reproducible.

## 5. Functional Test Cases

### 5.1 Lead Intake and Validation

| ID | Test | Expected Result |
|---|---|---|
| TC-01 | Submit a valid lead through the public form | Lead enters the common processing workflow |
| TC-02 | Register a valid lead through the internal form | Lead enters the common processing workflow with source `MANUAL` |
| TC-03 | Submit a valid lead through a webhook | Lead enters the common processing workflow with source `WEBHOOK` |
| TC-04 | Submit a valid lead through a compatible REST API request | Lead enters the common processing workflow with source `API` |
| TC-05 | Submit a lead without `first_name` | Submission is rejected |
| TC-06 | Submit a lead without email or phone | Submission is rejected |
| TC-07 | Submit an invalid email with a valid phone | Invalid email is discarded and processing continues |
| TC-08 | Submit an invalid email without a valid phone | Submission is rejected |
| TC-09 | Submit an email containing uppercase characters | Email is normalized to lowercase |
| TC-10 | Submit fields containing unnecessary whitespace | Whitespace is normalized |
| TC-11 | Submit a phone number requiring normalization | Phone is normalized without inventing a country code |
| TC-12 | Submit a lead with optional fields missing | Valid lead is processed without introducing invalid values |

### 5.2 Duplicate Detection and CRM Integrity

| ID | Test | Expected Result |
|---|---|---|
| TC-13 | Submit a lead with an existing normalized email | Existing lead is identified |
| TC-14 | Submit a lead with an existing normalized phone | Existing lead is identified |
| TC-15 | Email and phone match the same existing lead | Existing lead is updated where appropriate |
| TC-16 | Email matches one lead and phone matches another | No automatic update or merge; review item is created |
| TC-17 | Submit a lead with no matching email or phone | New lead is created |
| TC-18 | Update an existing lead with empty optional values | Existing valid values are preserved |
| TC-19 | Update an existing lead with invalid optional email and valid phone | Invalid email is not stored or used for matching |
| TC-20 | Register a new lead | Unique `lead_id`, default status `New`, and timestamps are assigned |
| TC-21 | Update an existing lead | `updated_at` is refreshed |
| TC-22 | Verify CRM write responsibility | Only WF-03 performs lead creation and update operations |

### 5.3 Conflict Review and Activity Logging

| ID | Test | Expected Result |
|---|---|---|
| TC-23 | Trigger conflicting email and phone matches | A record is created in `Review_Queue` |
| TC-24 | Trigger a duplicate conflict | `MANUAL_REVIEW_REQUIRED` is recorded |
| TC-25 | Verify duplicate conflict classification | No technical error is created in `Error_Log` |
| TC-26 | Set a review item to `IN_PROGRESS` | Review status is updated |
| TC-27 | Resolve a conflict by correcting relevant data | Resolution is recorded in `resolution_notes` |
| TC-28 | Resolve a conflict by keeping both leads separate | No automatic merge occurs and the resolution is recorded |
| TC-29 | Ignore a conflict | Review status becomes `IGNORED` |
| TC-30 | Match and update an existing lead | Relevant duplicate and update activity events are recorded where configured |

### 5.4 Notifications

| ID | Test | Expected Result |
|---|---|---|
| TC-31 | Register a new automated lead with a valid email | Owner notification and lead acknowledgement are sent |
| TC-32 | Register a new automated lead without a valid email but with a valid phone | Owner notification is sent; no lead acknowledgement |
| TC-33 | Register a new manual lead | Owner notification is sent; no automatic lead acknowledgement |
| TC-34 | Update an existing lead | No notification is sent by default |
| TC-35 | Trigger a duplicate conflict | Owner receives a review notification; no lead acknowledgement |
| TC-36 | Simulate a lead acknowledgement email failure | CRM registration remains valid and the email error is recorded |
| TC-37 | Simulate an owner notification failure | The relevant notification failure is recorded |
| TC-38 | Verify notification event logging | Successful email delivery and relevant notification activity are recorded without claiming success for failed deliveries |

### 5.5 Follow-up Lifecycle

| ID | Test | Expected Result |
|---|---|---|
| TC-39 | Create a follow-up with a valid date | Follow-up is created with status `PENDING` |
| TC-40 | Create a lead without a follow-up date | Follow-up fields remain empty |
| TC-41 | Create a follow-up for a lead that already has an active follow-up | Existing follow-up is rescheduled instead of creating a second one |
| TC-42 | Reschedule a previously notified follow-up | Date is replaced and `last_follow_up_notification_at` is cleared |
| TC-43 | Reschedule an active follow-up | `FOLLOW_UP_RESCHEDULED` is recorded |
| TC-44 | Complete a pending follow-up | Status becomes `COMPLETED` and the event is recorded |
| TC-45 | Cancel a pending follow-up | Status becomes `CANCELLED` and the event is recorded |
| TC-46 | Run the scheduler for a completed follow-up | No notification is sent |
| TC-47 | Run the scheduler for a cancelled follow-up | No notification is sent |
| TC-48 | Run the scheduler for a lead with status `Won` or `Lost` | No follow-up notification is sent |
| TC-49 | Run the scheduler repeatedly after a successfully recorded notification | No repeated notification is sent under normal operating conditions |

### 5.6 Follow-up Notification Failure Scenarios

| ID | Test | Expected Result |
|---|---|---|
| TC-50 | Simulate Gmail delivery failure | Notification timestamp is not updated and the email error is recorded |
| TC-51 | Simulate successful email delivery followed by a successful timestamp update | Notification timestamp is recorded |
| TC-52 | Simulate successful email delivery followed by failure to update Google Sheets | The partial failure is identified and documented; exactly-once delivery is not assumed |
| TC-53 | Re-run the scheduler after the partial failure in TC-52 | Actual behavior is verified; possible duplicate delivery is documented if the notification cannot be reliably reconciled |

### 5.7 Timezone, Error Handling, and Reporting

| ID | Test | Expected Result |
|---|---|---|
| TC-54 | Store a timestamp generated in the demonstration environment | Timestamp is stored in UTC ISO 8601 format |
| TC-55 | Interpret a locally entered follow-up date | Date is converted using the configured `Europe/Madrid` timezone |
| TC-56 | Simulate a CRM read or write failure | Appropriate technical error is recorded |
| TC-57 | Verify error message sanitization | Credentials, tokens, and unnecessary personal information are excluded |
| TC-58 | Generate basic lead reports | Total leads, status, source, pending follow-ups, and closed opportunities are available |
| TC-59 | Calculate conversion rate with no Won or Lost leads | Conversion rate is displayed as `N/A` |
| TC-60 | Calculate conversion rate with closed opportunities | Formula `Won / (Won + Lost) * 100` produces the expected result |

## 6. Concurrency and Data Integrity Tests

The following additional tests shall be performed specifically to verify the centralized CRM writer:

### CT-01 — Sequential Duplicate Submission

Submit the same lead twice in sequence.

**Expected result:** The second submission identifies the existing lead rather than creating an unnecessary duplicate.

### CT-02 — Simultaneous Duplicate Submission

Submit two identical leads as close together as possible.

**Expected result:** The system's actual execution behavior is observed and documented. Duplicate prevention must not be claimed unless the configuration demonstrates it.

### CT-03 — Simultaneous Different Input Channels

Submit matching lead information through two different input channels at approximately the same time.

**Expected result:** The centralized CRM writer handles the requests according to its verified serialization configuration.

### CT-04 — Conflicting Concurrent Matches

Submit information that produces conflicting email and phone matches while other CRM operations are running.

**Expected result:** Existing records are not automatically merged or incorrectly overwritten; unresolved cases are routed for manual review where detected.

### CT-05 — Writer Serialization Verification

Inspect the actual n8n execution configuration and test overlapping CRM operations.

**Expected result:** The implemented serialization behavior is demonstrated or its limitations are explicitly documented.

Google Sheets is not a transactional database. Search-before-insert alone is insufficient evidence of concurrency safety.

If reliable serialization cannot be demonstrated, the limitation must be documented before production use.

## 7. Integration Testing

Integration tests shall verify the complete path between:

- Public and internal n8n forms.
- Webhook and REST API input.
- Validation and normalization.
- Centralized CRM operations.
- Google Sheets worksheets.
- Gmail notifications.
- Scheduled follow-up processing.
- Error handling.

Each integration test shall verify both the resulting data and the relevant execution outcome.

## 8. Security and Privacy Testing

Testing shall verify that:

- Credentials are stored in n8n rather than hardcoded in workflows.
- Public exports contain no secrets.
- Logs do not expose authentication tokens.
- Review and error records contain only necessary information.
- Internal registration mechanisms are not unintentionally exposed as public forms.
- Access to the Google Sheets document and n8n editor is restricted appropriately.

## 9. Test Execution and Evidence

For each test, retain:

- Test ID.
- Test date and time.
- Input data or scenario.
- Expected result.
- Actual result.
- Pass or fail status.
- Relevant n8n execution reference.
- Sanitized screenshot or other evidence when useful.
- Notes describing any limitation or unexpected behavior.

Test evidence must use synthetic data and must not expose credentials or real personal information.

A test shall not be marked as passed without observable evidence of its expected result.

## 10. Acceptance Criteria

The project shall pass QA when:

- All applicable functional test cases have been executed.
- Lead registration works through all supported input channels.
- Validation and normalization rules behave consistently.
- Duplicate detection and manual conflict handling are verified.
- Notifications follow the defined notification policy.
- Follow-up creation, rescheduling, completion, and cancellation are verified.
- Notification failure scenarios are tested and documented.
- Technical errors are logged and sanitized.
- Timezone handling is verified.
- Reporting calculations are correct.
- Concurrency behavior is demonstrated or its limitations are documented.
- Security and privacy checks have been completed.

Unresolved critical failures shall prevent production-readiness approval.

## 11. Current Testing Status

**Test plan:** Defined and updated in Version 1.2.  
**Functional tests:** Pending execution.  
**Integration tests:** Pending execution.  
**Concurrency tests:** Pending execution.  
**Notification failure tests:** Pending execution.  
**Security checks:** Pending execution.  
**QA approval:** Not granted.

No test result or production-readiness claim shall be made until supported by actual execution evidence.
