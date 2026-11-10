# ZUNPY Lead Management Automation
## Document 02 — Requirements Specification

**Version:** 1.1  
**Status:** Requirements defined; implementation and verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose

This document defines the functional and non-functional requirements for the ZUNPY Lead Management Automation project.

The system will centralize lead registration, validation, duplicate detection, activity tracking, notifications, follow-up management, and basic reporting.

The solution is designed as a small, maintainable portfolio project using n8n, Google Sheets, Gmail, and standard webhooks or REST APIs.

It is not intended to replace a complete CRM platform.

## 2. Project Scope

### 2.1 Included in Version 1

- Automated lead capture through a public n8n form.
- Manual lead registration through an internal form.
- Lead capture through webhooks and compatible REST APIs.
- Common validation and normalization.
- Duplicate detection using email and phone.
- Centralized lead storage in Google Sheets.
- Activity history and technical error logging.
- Manual review of conflicting duplicate matches.
- Owner notifications and automated lead acknowledgements.
- Basic lead status management.
- Follow-up scheduling and notifications.
- Basic reporting.
- Documentation and reproducible deployment configuration.

### 2.2 Out of Scope

- A complete CRM platform.
- Advanced sales pipeline management.
- Marketing campaigns and bulk email.
- Multiple simultaneous active follow-ups per lead.
- Advanced analytics and forecasting.
- Complex role-based access control.
- Mandatory paid integrations.
- Database migration unless Google Sheets proves unsuitable for the required data-integrity controls.

## 3. Functional Requirements

### FR-01 — Automated Lead Capture

The system shall accept leads through:

- A public n8n form.
- Webhooks.
- Compatible REST API integrations.

All automated input methods shall use the same validation, duplicate detection, and CRM processing path.

The original input method shall be recorded in the lead's `source` field.

### FR-02 — Manual Lead Registration

The system shall provide an internal form for authorized users to register leads manually.

Manual registrations shall use the same validation and duplicate detection rules as automated registrations.

The lead source shall be recorded as `MANUAL`.

Manual registration shall not trigger an automatic acknowledgement email to the lead by default.

### FR-03 — Data Validation and Normalization

The system shall:

- Require `first_name`.
- Require at least one valid contact method: email or phone.
- Trim unnecessary whitespace.
- Normalize email addresses to lowercase.
- Validate supplied email addresses.
- Validate phone numbers without inventing a country code.
- Reject submissions that do not contain at least one valid contact method.

If an email address is supplied but invalid, while the phone number is valid, the system shall discard the invalid email value and may continue processing the lead using the valid phone number.

An invalid email address shall not be stored or used for duplicate matching.

If no valid contact method remains, the submission shall be rejected.

The system shall not overwrite existing valid lead information with empty or invalid incoming values.

### FR-04 — Duplicate Detection and Conflict Management

The system shall detect possible duplicates using:

1. Normalized email as the primary matching criterion.
2. Normalized phone number as a secondary matching criterion.

When both matching criteria identify the same existing lead, the system shall update that record where appropriate.

Existing valid information shall be preserved when incoming values are empty or invalid.

When no matching lead exists, the system shall create a new lead.

If email and phone matches identify two different existing leads, the system shall:

- Avoid automatically merging the records.
- Avoid updating either matched lead.
- Create a review item in `Review_Queue`.
- Record the review event in `Activity_Log`.
- Notify the owner that manual review is required.

The owner shall be able to resolve the conflict by correcting the relevant data, keeping the records separate, or ignoring the case.

The resolution and its notes shall be recorded. Automatic record merging is not supported in Version 1.

Duplicate conflicts are business-data review cases, not technical errors, and shall not be recorded as technical failures in `Error_Log`.

### FR-05 — Centralized CRM Storage

The system shall use one Google Sheets document containing four worksheets:

- `Leads`
- `Activity_Log`
- `Error_Log`
- `Review_Queue`

Each lead shall have a unique `lead_id`.

The `Leads` worksheet shall contain the following fields:

- `lead_id`
- `first_name`
- `last_name`
- `email`
- `phone`
- `company`
- `source`
- `message`
- `status`
- `created_at`
- `updated_at`
- `follow_up_date`
- `follow_up_status`
- `last_follow_up_notification_at`
- `notes`

Timestamps shall be stored in UTC using ISO 8601 format.

The default display timezone for the demonstration environment shall be `Europe/Madrid`, configurable for other deployments.

All CRM lead creation and update operations shall be handled through a centralized CRM writer workflow.

### FR-06 — Email Acknowledgement

The system shall send an acknowledgement email to a lead when:

- The lead was registered through an automated input method.
- The registration was successful.
- A valid email address is available.

Manual registrations shall not receive an acknowledgement email by default.

Existing lead updates shall not trigger an acknowledgement email by default.

A duplicate conflict requiring manual review shall not trigger an acknowledgement email.

Email delivery failure shall not undo or invalidate a successful CRM registration.

### FR-07 — Owner Notifications

The system shall notify the configured owner after a new lead has been successfully registered.

The notification policy shall be:

| Event | Owner notification | Lead acknowledgement |
|---|---|---|
| New automated lead | Yes | Yes, if valid email exists |
| New manual lead | Yes | No, by default |
| Existing lead update | No, by default | No, by default |
| Duplicate conflict | Yes, for manual review | No |
| Due follow-up | Yes | Not included in Version 1 |
| Critical technical error | Yes, when configured | No |

Notification failures shall be logged without undoing successful CRM operations.

### FR-08 — Lead Status Management

The system shall support the following lead statuses:

- `New`
- `Contacted`
- `Qualified`
- `Proposal Sent`
- `Won`
- `Lost`

Version 1 shall validate allowed status values but shall not enforce a rigid status-transition graph.

Authorized status changes shall be recorded in `Activity_Log`.

Leads marked `Won` or `Lost` shall be excluded from scheduled follow-up notifications.

### FR-09 — Follow-up Management

The system shall support one active follow-up per lead.

The follow-up fields shall be:

- `follow_up_date`
- `follow_up_status`
- `last_follow_up_notification_at`

The allowed follow-up statuses shall be:

- `PENDING`
- `COMPLETED`
- `CANCELLED`

When a follow-up date is created, its initial status shall be `PENDING`.

If no follow-up date exists, the related follow-up fields shall remain empty.

Creating a new follow-up for a lead that already has an active follow-up shall reschedule the existing follow-up instead of creating a second active one.

When a follow-up is rescheduled:

- The existing follow-up date shall be replaced.
- Its status shall remain or become `PENDING`.
- `last_follow_up_notification_at` shall be cleared.
- The rescheduling event shall be recorded as `FOLLOW_UP_RESCHEDULED`.

Completing or cancelling a follow-up shall remove it from the active follow-up process.

The scheduler shall notify the owner when a pending follow-up becomes due.

By default, only one successful notification shall be recorded for each due follow-up. Additional reminders require an explicitly configured policy.

The notification timestamp shall be updated only after successful email delivery and successful recording of that delivery.

The system shall use a duplicate-notification guard and shall test failure scenarios. However, Gmail and Google Sheets do not provide a shared atomic transaction, so exactly-once delivery cannot be guaranteed in every failure scenario.

### FR-10 — Activity History

The system shall record relevant lead and follow-up events in `Activity_Log`.

Supported event types shall include:

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

Activity sources shall use:

- `SYSTEM`
- `MANUAL`
- `AUTOMATED`

These values are distinct from the lead input source values.

### FR-11 — Technical Error Logging

The system shall record relevant technical errors in `Error_Log`.

Supported error categories shall include:

- `CRM_READ_ERROR`
- `CRM_WRITE_ERROR`
- `EMAIL_ERROR`
- `WORKFLOW_ERROR`

Each error record shall contain the relevant workflow, execution, lead reference when available, sanitized error information, timestamp, and resolution status.

Validation rejections and duplicate conflicts shall not be classified as technical errors.

Sensitive credentials, tokens, and unnecessary personal information shall not be included in error messages.

### FR-12 — Basic Reporting

The system shall provide basic reporting information, including:

- Total number of leads.
- New leads.
- Leads grouped by status.
- Leads grouped by source.
- Pending follow-ups.
- Won and Lost leads.
- Lead conversion rate.

The conversion rate shall be calculated as:

`Won / (Won + Lost) * 100`

If there are no closed opportunities (`Won` or `Lost`), the conversion rate shall be displayed as `N/A`.

## 4. Data and Business Rules

- Every lead must have a unique `lead_id`.
- `first_name` is mandatory.
- At least one valid contact method is mandatory.
- The lead source must be one of `FORM`, `WEBHOOK`, `MANUAL`, or `API`.
- New leads shall receive the default status `New`.
- Email matching shall use normalized lowercase values.
- Phone matching shall use normalized phone values without inventing country codes.
- Existing valid information shall not be overwritten by empty or invalid values.
- Conflicting email and phone matches require manual review.
- Review items shall use `OPEN`, `IN_PROGRESS`, `RESOLVED`, or `IGNORED`.
- A lead may have only one active follow-up.
- Follow-up timestamps shall be stored in UTC.
- Activity source values shall be `SYSTEM`, `MANUAL`, or `AUTOMATED`.
- CRM writes shall be centralized and serialized where the actual n8n configuration permits.
- Google Sheets does not provide transactional uniqueness guarantees. The implementation must demonstrate its concurrency controls and document any remaining limitations.

## 5. Non-Functional Requirements

### NFR-01 — Reliability

The system shall handle invalid input, duplicate conflicts, and integration failures without silently corrupting existing lead data.

### NFR-02 — Security and Privacy

Credentials shall be stored securely in n8n.

Sensitive information shall not be included in public GitHub exports or unnecessary logs.

Access to forms, workflows, and Google Sheets shall be appropriately restricted.

### NFR-03 — Maintainability

Workflows shall have clear responsibilities and use centralized CRM write operations.

Data fields, statuses, event types, and error categories shall be documented consistently.

### NFR-04 — Reproducibility

The project shall include sanitized workflow exports, configuration instructions, and test documentation.

### NFR-05 — Cost

The initial implementation shall prioritize n8n, Google Sheets, and Gmail without requiring additional paid services.

### NFR-06 — Data Integrity

Concurrent CRM operations shall be tested.

The implementation shall not claim guaranteed duplicate prevention under concurrency unless the actual storage and execution configuration demonstrates that guarantee.

## 6. Acceptance Criteria

| ID | Acceptance criterion |
|---|---|
| AC-01 | A valid public form submission creates a lead. |
| AC-02 | A valid manual registration creates a lead using the common processing path. |
| AC-03 | An invalid optional email is discarded when a valid phone remains. |
| AC-04 | A submission without any valid contact method is rejected. |
| AC-05 | A matching normalized email identifies an existing lead. |
| AC-06 | A matching phone identifies an existing lead. |
| AC-07 | Conflicting email and phone matches create a review item without automatic merging or updating either lead. |
| AC-08 | Successful automated registration sends the configured acknowledgement when a valid email exists. |
| AC-09 | New lead registration notifies the configured owner. |
| AC-10 | Valid status changes are recorded in the activity history. |
| AC-11 | A new follow-up starts with `PENDING`; rescheduling updates the existing follow-up and resets its notification timestamp. |
| AC-12 | Completed and cancelled follow-ups are excluded from future scheduled notifications. |
| AC-13 | Repeated scheduler executions do not resend a successfully recorded follow-up notification under normal operating conditions. |
| AC-14 | Notification failure is logged without undoing successful lead registration. |
| AC-15 | Technical processing errors are recorded in `Error_Log` with sanitized information. |
| AC-16 | Duplicate conflicts and validation rejections are not recorded as technical errors. |
| AC-17 | Basic reporting displays the defined lead and follow-up metrics. |
| AC-18 | Concurrent submissions are tested against the centralized CRM writer and documented integrity limitations. |
| AC-19 | Follow-up notification failure scenarios are tested, including failures between email delivery and notification timestamp recording. |
| AC-20 | Review items can be resolved or ignored with a recorded outcome and without automatic record merging. |

## 7. Definition of Done

Version 1 shall be considered complete when:

- All in-scope workflows have been implemented.
- Functional acceptance criteria have been tested.
- Duplicate detection and conflict review have been verified.
- CRM write serialization has been demonstrated or its limitations explicitly documented.
- Follow-up lifecycle and notification failure scenarios have been tested.
- Error handling and notification behavior have been verified.
- No credentials or private configuration data are included in public exports.
- Sanitized workflow exports and project documentation are available.
- Evidence of successful tests is retained for portfolio purposes.

## 8. Current Project Status

**Requirements:** Defined and updated in Version 1.1.  
**Architecture:** Defined.  
**Implementation:** Pending.  
**Testing:** Pending.  
**Deployment:** Pending.

No implementation or production-readiness claim is made until the corresponding work has been completed and verified.
