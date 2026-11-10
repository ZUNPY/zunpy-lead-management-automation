# ZUNPY Lead Management Automation
## Document 04 — Workflow Design

**Version:** 1.2  
**Status:** Workflow design defined; implementation and verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose

This document describes the workflow architecture and operational logic of the ZUNPY Lead Management Automation system.

The solution uses n8n to coordinate lead intake, validation, duplicate detection, centralized CRM operations, email notifications, follow-up scheduling, and technical error handling.

The design prioritizes clear workflow responsibilities, consistent data processing, and controlled CRM writes.

## 2. Workflow Overview

The system consists of six main workflows:

| Workflow | Name | Responsibility |
|---|---|---|
| WF-01 | Lead Intake | Receive leads from supported input channels |
| WF-02 | Lead Validation | Validate and normalize incoming data |
| WF-03 | CRM Operations | Detect duplicates and perform centralized CRM operations |
| WF-04 | Email Notifications | Send owner notifications and lead acknowledgements |
| WF-05 | Follow-up Scheduler | Manage scheduled follow-ups and owner reminders |
| WF-06 | Error Handling | Record and manage technical failures |

The workflows communicate through defined input and output data structures.

WF-03 is the only workflow authorized to create or update records in the `Leads` worksheet.

## 3. WF-01 — Lead Intake

### 3.1 Purpose

Receive lead information from different sources and convert it into a common input structure.

### 3.2 Input Channels

- Public n8n form.
- Internal manual registration form.
- Webhooks.
- Compatible REST API integrations.

### 3.3 Processing Logic

1. Receive the incoming payload.
2. Identify the input channel.
3. Assign the corresponding source value.
4. Map available fields into the common lead payload.
5. Pass the payload to WF-02.

### 3.4 Lead Source Values

The `source` field shall use one of the following values:

- `FORM`
- `WEBHOOK`
- `MANUAL`
- `API`

These values describe how the lead entered the system.

They are separate from the activity source values used in `Activity_Log`.

### 3.5 Common Input Structure

The normalized input structure shall support:

- `first_name`
- `last_name`
- `email`
- `phone`
- `company`
- `message`
- `source`

Additional internal metadata may be passed between workflows when required.

### 3.6 Output

A common lead payload sent to WF-02.

Invalid or incomplete submissions shall be handled by the validation workflow rather than bypassing the common processing path.

## 4. WF-02 — Lead Validation

### 4.1 Purpose

Validate and normalize incoming lead data before CRM processing.

### 4.2 Validation Rules

- `first_name` is mandatory.
- At least one valid contact method must remain after validation.
- Email addresses must have a valid format.
- Phone numbers must pass the configured validation rules.
- Unnecessary whitespace must be removed.
- Email addresses must be converted to lowercase.
- Phone numbers must be normalized without inventing country codes.

### 4.3 Optional Invalid Email Handling

If an incoming email address is invalid but the phone number is valid:

1. Discard the invalid email value.
2. Do not store or use the invalid email for duplicate matching.
3. Continue processing using the valid phone number.

If no valid contact method remains, reject the submission.

### 4.4 Data Preservation

The validation process must not introduce empty or invalid values that could overwrite existing valid CRM information.

### 4.5 Output

A validated and normalized lead payload sent to WF-03.

If validation fails, the workflow shall return a rejected result.

Validation rejections are not technical errors and shall not be recorded as technical failures in `Error_Log`.

## 5. WF-03 — CRM Operations

### 5.1 Purpose

Centralize lead creation, duplicate detection, lead updates, and conflict management.

This workflow is the only authorized writer of lead records in the `Leads` worksheet.

### 5.2 Processing Logic

1. Receive the validated lead payload.
2. Search for an existing lead using normalized email, when available.
3. Search for an existing lead using normalized phone, when available.
4. Compare the matching results.
5. Determine whether to create, update, or request manual review.
6. Perform the corresponding CRM operation.
7. Record the relevant activity.
8. Return a structured operation result.

### 5.3 Duplicate Detection Rules

**Case A — No matching record**

Create a new lead with:

- A unique `lead_id`.
- Default status `New`.
- The appropriate input source.
- `created_at` and `updated_at` timestamps in UTC.

If no follow-up date is supplied, follow-up fields remain empty.

**Case B — Email and phone identify the same existing lead**

Update the existing lead where appropriate.

Preserve existing valid information when incoming values are empty or invalid.

Update `updated_at` and record the relevant activity.

**Case C — Only email matches an existing lead**

Update the matching record where appropriate, preserving valid existing information.

**Case D — Only phone matches an existing lead**

Update the matching record where appropriate, preserving valid existing information.

**Case E — Email and phone identify different existing leads**

Do not automatically merge or update either lead.

Instead:

1. Create a record in `Review_Queue`.
2. Record the conflict in `Activity_Log` using `MANUAL_REVIEW_REQUIRED`.
3. Notify the configured owner.
4. Return a result requiring manual review.

A duplicate conflict is a business-data issue, not a technical error.

### 5.4 Manual Conflict Resolution

The owner shall review the relevant records and choose one of the following outcomes:

- Correct the relevant data and resolve the review item.
- Keep both records separate and resolve the review item.
- Ignore the case.

The resolution shall be recorded in `Review_Queue` using:

- `review_status`
- `resolution_notes`

Allowed review statuses:

- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`
- `IGNORED`

Version 1 does not implement automatic record merging.

### 5.5 Centralized CRM Write Control

All lead creation and update operations must pass through WF-03.

The implementation must configure and verify serialized CRM writes using the actual n8n execution configuration.

Google Sheets does not provide transactional uniqueness guarantees.

If reliable serialization cannot be demonstrated, the limitation must be documented. A transactional database may be considered later if the integrity requirements cannot be met with the initial storage design.

A search-before-insert sequence alone must not be treated as proof of concurrency safety.

### 5.6 Activity Logging

Relevant events shall be recorded in `Activity_Log`.

Supported event types:

- `LEAD_CREATED`
- `LEAD_UPDATED`
- `STATUS_CHANGED`
- `DUPLICATE_DETECTED`
- `MANUAL_REVIEW_REQUIRED`
- `FOLLOW_UP_CREATED`
- `FOLLOW_UP_RESCHEDULED`
- `FOLLOW_UP_COMPLETED`
- `FOLLOW_UP_CANCELLED`
- `FOLLOW_UP_NOTIFICATION_SENT`
- `EMAIL_SENT`

When an existing lead is matched, `DUPLICATE_DETECTED` may be recorded alongside `LEAD_UPDATED`.

Activity source values:

- `SYSTEM`
- `MANUAL`
- `AUTOMATED`

These values describe who or what generated the activity.

They must not be confused with the lead input source values stored in `Leads.source`.

### 5.7 Output Contract

WF-03 shall return a structured result containing:

| Field | Description |
|---|---|
| `lead_id` | Relevant lead identifier, when available |
| `operation_type` | `CREATED`, `UPDATED`, `CONFLICT`, `REJECTED`, or `FAILED` |
| `operation_status` | `SUCCESS`, `REVIEW_REQUIRED`, `REJECTED`, or `FAILED` |
| `source` | Original lead input source |
| `processed_at` | Processing timestamp in UTC |
| `review_id` | Review item identifier, when applicable |
| `error_id` | Technical error identifier, when applicable |

The operation result shall distinguish successful CRM operations from manual review, validation rejection, and technical failure.

## 6. WF-04 — Email Notifications

### 6.1 Purpose

Manage owner notifications and lead acknowledgement emails.

### 6.2 Notification Rules

| Event | Owner notification | Lead acknowledgement |
|---|---|---|
| New automated lead | Yes | Yes, if valid email exists |
| New manual lead | Yes | No, by default |
| Existing lead update | No, by default | No, by default |
| Duplicate conflict | Yes, for manual review | No |
| Due follow-up | Yes | Not included in Version 1 |
| Critical technical error | Yes, when configured | No |

### 6.3 Notification Processing

1. Receive the relevant event or operation result.
2. Determine the notification type.
3. Verify that the required recipient and configuration are available.
4. Send the appropriate email.
5. Record successful notification activity.
6. Report delivery failures to WF-06.

### 6.4 Email Failure Handling

An email failure must not undo a successful CRM operation.

Email errors shall be recorded in `Error_Log` using the `EMAIL_ERROR` category.

A notification failure must not be reported as a successful email delivery.

The system shall not send lead acknowledgements for rejected submissions or duplicate conflicts requiring manual review.

## 7. WF-05 — Follow-up Scheduler

### 7.1 Purpose

Check pending follow-ups and notify the configured owner when they become due.

### 7.2 Follow-up Data

The `Leads` worksheet shall contain:

- `follow_up_date`
- `follow_up_status`
- `last_follow_up_notification_at`

Allowed follow-up statuses:

- `PENDING`
- `COMPLETED`
- `CANCELLED`

When a follow-up date is first created, its status shall be `PENDING`.

If no follow-up date exists, the related follow-up fields shall remain empty.

### 7.3 Follow-up Creation

When a user schedules a follow-up:

1. Verify the lead exists.
2. Check whether an active follow-up already exists.
3. If none exists, create a pending follow-up.
4. Record `FOLLOW_UP_CREATED`.
5. If an active follow-up exists, reschedule that follow-up instead of creating another one.

### 7.4 Follow-up Rescheduling

When an active follow-up is rescheduled:

1. Replace the existing `follow_up_date`.
2. Keep or set `follow_up_status` to `PENDING`.
3. Clear `last_follow_up_notification_at`.
4. Record `FOLLOW_UP_RESCHEDULED`.
5. Continue using the existing lead and follow-up record.

Rescheduling must not create a second active follow-up.

### 7.5 Follow-up Completion and Cancellation

When a follow-up is completed:

- Set `follow_up_status` to `COMPLETED`.
- Record `FOLLOW_UP_COMPLETED`.

When a follow-up is cancelled:

- Set `follow_up_status` to `CANCELLED`.
- Record `FOLLOW_UP_CANCELLED`.

Completed and cancelled follow-ups shall be excluded from future scheduler notifications.

### 7.6 Scheduler Rules

The scheduler shall:

1. Identify leads with a pending follow-up.
2. Check whether the follow-up date is due.
3. Exclude leads with status `Won` or `Lost`.
4. Check the notification timestamp and notification guard.
5. Notify the configured owner when appropriate.
6. Record successful notifications.

By default, one successful notification is allowed per due follow-up.

Additional reminders require an explicitly configured policy.

### 7.7 Notification Idempotency and Failure Handling

The scheduler shall use a notification guard to avoid sending repeated reminders after a successful notification has been recorded.

`last_follow_up_notification_at` shall be updated only after successful email delivery and successful recording of that delivery.

The implementation must account for the possibility that an email is delivered but the subsequent timestamp update fails.

Because Gmail and Google Sheets do not provide a shared atomic transaction, exactly-once delivery cannot be guaranteed in every failure scenario.

Such scenarios must be tested and any remaining limitation documented.

### 7.8 Timezone Handling

- Store timestamps in UTC using ISO 8601.
- Use a configurable local timezone for date interpretation and display.
- The demonstration environment shall use `Europe/Madrid`.
- Convert locally entered follow-up dates to UTC before storage.

## 8. WF-06 — Error Handling

### 8.1 Purpose

Centralize the recording and management of technical workflow failures.

### 8.2 Error Categories

- `CRM_READ_ERROR`
- `CRM_WRITE_ERROR`
- `EMAIL_ERROR`
- `WORKFLOW_ERROR`

### 8.3 Processing Logic

1. Receive a technical error from a workflow.
2. Identify the originating workflow and execution.
3. Identify the related lead, when available.
4. Sanitize the error information.
5. Create a record in `Error_Log`.
6. Notify the configured owner when the error meets the critical notification policy.
7. Make the error available for later review.

### 8.4 Error Classification

The following are not technical errors:

- Invalid input rejected during validation.
- Duplicate conflicts requiring manual review.
- Normal business-rule decisions.

These outcomes shall be handled by their respective workflows and recorded where appropriate.

### 8.5 Error Log Fields

The `Error_Log` worksheet shall contain:

- `error_id`
- `workflow_name`
- `execution_id`
- `lead_id`
- `error_category`
- `error_message`
- `occurred_at`
- `resolution_status`

Sensitive credentials, tokens, and unnecessary personal information must not be included in error messages.

## 9. Inter-Workflow Communication

Workflows shall exchange structured payloads rather than relying on undocumented assumptions.

The main CRM operation response shall include:

- `lead_id`
- `operation_type`
- `operation_status`
- `source`
- `processed_at`
- `review_id`
- `error_id`

Optional fields shall be included only when applicable.

The result must distinguish:

| Situation | `operation_type` | `operation_status` |
|---|---|---|
| New lead created | `CREATED` | `SUCCESS` |
| Existing lead updated | `UPDATED` | `SUCCESS` |
| Conflicting duplicate matches | `CONFLICT` | `REVIEW_REQUIRED` |
| Validation rejection | `REJECTED` | `REJECTED` |
| Technical processing failure | `FAILED` | `FAILED` |

This contract provides a consistent basis for notifications, activity logging, error handling, and testing.

## 10. Execution and Data Integrity Considerations

- WF-03 is the only workflow allowed to write lead records.
- CRM write operations must be serialized where supported by the actual n8n configuration.
- The implementation must verify concurrency behavior through testing.
- Google Sheets must not be treated as a transactional database.
- Duplicate detection and conflict handling must preserve existing valid information.
- Notification processing must not invalidate successful CRM operations.
- Workflow failures must be distinguishable from business-rule outcomes.

## 11. Implementation Status

**Workflow design:** Defined in Version 1.2.  
**Workflow implementation:** Pending.  
**Execution configuration:** Pending verification.  
**Concurrency tests:** Pending.  
**Notification failure tests:** Pending.  
**Production readiness:** Not established.
