# ZUNPY Lead Management Automation
## Document 08 — Deployment and Configuration Guide

**Version:** 1.2  
**Status:** Deployment guide defined; deployment and verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose

This document describes the environment requirements, configuration, deployment procedure, and operational checks for ZUNPY Lead Management Automation.

It is intended to provide reproducible deployment instructions for the Version 1 implementation.

The guide describes the required configuration but does not claim that deployment or production readiness has already been verified.

## 2. Technology Requirements

The initial deployment uses:

| Component | Purpose |
|---|---|
| n8n | Workflow automation and orchestration |
| Google Sheets | Centralized CRM data storage |
| Gmail | Owner notifications and lead acknowledgements |
| n8n Forms | Public and internal lead registration |
| Webhooks and REST APIs | External lead intake |
| GitHub | Version control and sanitized workflow exports |

Python may be used for additional processing only when justified by an implementation requirement.

No additional paid service is mandatory for the initial deployment.

## 3. Environment Prerequisites

Before deployment, prepare:

- An accessible n8n instance.
- A Google account with permission to create and manage the CRM spreadsheet.
- Gmail access for operational notifications.
- An authorized owner notification email address.
- Access to configure n8n credentials.
- A development or test environment.
- A GitHub repository for project documentation and sanitized exports.

The owner notification recipient must be configured before testing notification workflows.

## 4. Google Sheets Configuration

### 4.1 Create the CRM Spreadsheet

Create one Google Sheets document named:

`ZUNPY Lead Management CRM`

Create the following four worksheets:

1. `Leads`
2. `Activity_Log`
3. `Error_Log`
4. `Review_Queue`

### 4.2 Leads Worksheet

Create these columns in the specified order:

| Column | Field |
|---|---|
| A | `lead_id` |
| B | `first_name` |
| C | `last_name` |
| D | `email` |
| E | `phone` |
| F | `company` |
| G | `source` |
| H | `message` |
| I | `status` |
| J | `created_at` |
| K | `updated_at` |
| L | `follow_up_date` |
| M | `follow_up_status` |
| N | `last_follow_up_notification_at` |
| O | `notes` |

### 4.3 Activity_Log Worksheet

| Column | Field |
|---|---|
| A | `activity_id` |
| B | `lead_id` |
| C | `event_type` |
| D | `source` |
| E | `description` |
| F | `timestamp` |
| G | `execution_id` |

Supported activity sources:

- `SYSTEM`
- `MANUAL`
- `AUTOMATED`

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

### 4.4 Error_Log Worksheet

| Column | Field |
|---|---|
| A | `error_id` |
| B | `workflow_name` |
| C | `execution_id` |
| D | `lead_id` |
| E | `error_category` |
| F | `error_message` |
| G | `occurred_at` |
| H | `resolution_status` |

Supported error categories:

- `CRM_READ_ERROR`
- `CRM_WRITE_ERROR`
- `EMAIL_ERROR`
- `WORKFLOW_ERROR`

Validation rejections and duplicate conflicts must not be classified as technical errors.

### 4.5 Review_Queue Worksheet

| Column | Field |
|---|---|
| A | `review_id` |
| B | `detected_at` |
| C | `email_match_lead_id` |
| D | `phone_match_lead_id` |
| E | `source` |
| F | `review_reason` |
| G | `review_status` |
| H | `resolution_notes` |

Supported review statuses:

- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`
- `IGNORED`

The owner must be able to record the resolution without automatically merging the involved leads.

### 4.6 Spreadsheet Access

- Grant access only to authorized users and required integrations.
- Avoid public spreadsheet sharing.
- Use the appropriate Google credential in n8n.
- Do not include real customer information in demonstration records.
- Keep backups and exported copies subject to the same privacy controls.

## 5. n8n Credentials and Configuration

### 5.1 Google Sheets Credentials

Configure the required Google authentication in n8n.

Verify that the configured credential can access the CRM spreadsheet and perform the required read and write operations.

### 5.2 Gmail Credentials

Configure Gmail authentication in n8n.

Verify that the integration can send the required operational emails.

Configure the owner notification recipient.

Use a test recipient during development.

### 5.3 General Configuration

The following configuration values shall be defined:

| Setting | Demonstration value |
|---|---|
| Local timezone | `Europe/Madrid` |
| Timestamp storage | UTC |
| CRM spreadsheet | `ZUNPY Lead Management CRM` |
| Lead default status | `New` |
| Owner notification recipient | Configured deployment value |
| Follow-up default status | `PENDING` |

Credentials, tokens, and private identifiers must be stored in n8n credentials or appropriate private configuration, not hardcoded in public workflow exports.

## 6. Workflow Deployment

Deploy the six workflows described in Document 04:

| Workflow | Name | Purpose |
|---|---|---|
| WF-01 | Lead Intake | Receive leads from supported channels |
| WF-02 | Lead Validation | Validate and normalize input |
| WF-03 | CRM Operations | Centralized CRM reads, duplicate detection, and writes |
| WF-04 | Email Notifications | Owner notifications and lead acknowledgements |
| WF-05 | Follow-up Scheduler | Scheduled follow-up processing |
| WF-06 | Error Handling | Centralized technical error recording |

### 6.1 Deployment Rules

- Import or create workflows using the documented structure.
- Configure credentials separately from workflow definitions.
- Verify all Google Sheets document and worksheet references.
- Verify workflow-to-workflow communication.
- Ensure WF-03 is the only workflow authorized to create or update lead records.
- Ensure error and notification handling do not invalidate successful CRM registration.

### 6.2 CRM Write Serialization

CRM creation and update operations must be centralized through WF-03.

Configure serialized execution using the actual n8n execution and concurrency capabilities available in the deployment environment.

Verify the behavior through overlapping submission tests.

Do not assume that a search-before-insert sequence or a single writer workflow automatically guarantees uniqueness.

Google Sheets does not provide transactional uniqueness guarantees.

If reliable serialization cannot be demonstrated, document the limitation and evaluate whether a transactional database is necessary before production use.

## 7. Lead Input Configuration

### 7.1 Public Form

Configure a public n8n form with the required lead fields.

The form shall:

- Collect the first name.
- Accept email and/or phone.
- Allow optional company and message fields.
- Pass the source as `FORM`.
- Send the submission to WF-01.

### 7.2 Internal Manual Form

Configure a separate internal form for authorized users.

The form shall:

- Use the same common processing path.
- Assign source `MANUAL`.
- Avoid automatic lead acknowledgement by default.
- Require appropriate access restrictions.

### 7.3 Webhook and REST API

Configure webhook and API input structures according to the common lead payload defined in Document 04.

Allowed source values:

- `WEBHOOK`
- `API`

External integrations must not bypass validation or centralized CRM operations.

## 8. Notification Configuration

Configure the notification policy as follows:

| Event | Owner notification | Lead acknowledgement |
|---|---|---|
| New automated lead | Yes | Yes, if valid email exists |
| New manual lead | Yes | No, by default |
| Existing lead update | No, by default | No, by default |
| Duplicate conflict | Yes, for manual review | No |
| Due follow-up | Yes | Not included in Version 1 |
| Critical technical error | Yes, when configured | No |

Email delivery failures must be recorded without undoing successful CRM operations.

Successful notification activity must be recorded only after the relevant delivery succeeds.

## 9. Follow-up Configuration

The follow-up process shall use:

- `follow_up_date`
- `follow_up_status`
- `last_follow_up_notification_at`

Allowed statuses:

- `PENDING`
- `COMPLETED`
- `CANCELLED`

Configuration rules:

- A new follow-up starts as `PENDING`.
- A lead may have only one active follow-up.
- A new follow-up date reschedules the existing active follow-up.
- Rescheduling clears `last_follow_up_notification_at`.
- Rescheduling records `FOLLOW_UP_RESCHEDULED`.
- Completed and cancelled follow-ups are excluded from scheduler notifications.
- Leads with status `Won` or `Lost` are excluded.
- Additional reminders are disabled unless an explicit policy is configured.

### 9.1 Notification Failure Considerations

The scheduler must use a notification guard to avoid repeating successfully recorded notifications under normal operating conditions.

The notification timestamp must be updated only after successful email delivery and successful recording of the delivery.

A failure between email delivery and the Google Sheets update may leave the system unable to determine reliably whether the notification was already delivered.

Gmail and Google Sheets do not provide a shared atomic transaction. Exactly-once delivery must not be claimed.

This limitation must be verified and documented during testing.

## 10. Timezone Configuration

- Store timestamps in UTC ISO 8601 format.
- Configure the local timezone for date interpretation and display.
- Use `Europe/Madrid` for the demonstration environment.
- Convert locally entered follow-up dates to UTC before storage.
- Verify scheduler behavior around timezone changes and daylight-saving transitions.

## 11. Security Configuration

Before exposing any input endpoint:

- Restrict access to the n8n editor.
- Protect internal forms.
- Use HTTPS for publicly accessible endpoints.
- Apply appropriate webhook access controls.
- Store credentials securely.
- Restrict Google Sheets permissions.
- Avoid exposing unnecessary personal information.
- Review workflow exports before publishing them.

The public form must collect only the information required by the project.

## 12. Backup and Recovery

The deployment shall include a documented backup approach for:

- The Google Sheets CRM data.
- n8n workflow definitions.
- Relevant n8n configuration.
- Project documentation.

Backups must be stored securely and must not be included in public repositories when they contain private information.

Recovery procedures shall be tested before production use.

## 13. Deployment Verification Checklist

Before production activation, verify:

- [ ] n8n is accessible and configured.
- [ ] Google Sheets credentials work.
- [ ] Gmail credentials work.
- [ ] Owner notification recipient is configured.
- [ ] All four worksheets exist with the correct columns.
- [ ] All six workflows are configured.
- [ ] Public and internal forms work.
- [ ] Webhook and REST API input use the common processing path.
- [ ] Validation and normalization work correctly.
- [ ] Duplicate detection and conflict review work correctly.
- [ ] Only WF-03 writes lead records.
- [ ] CRM write serialization is demonstrated or its limitations are documented.
- [ ] Notification rules are verified.
- [ ] Follow-up creation and rescheduling work correctly.
- [ ] Notification timestamp reset is verified.
- [ ] Partial notification failure scenarios are tested.
- [ ] Timezone handling is verified.
- [ ] Error logging and sanitization work.
- [ ] Security and backup checks are completed.
- [ ] Functional and integration tests have passed.

Production activation must not be approved while critical failures remain unresolved.

## 14. Current Deployment Status

**Deployment guide:** Defined and updated in Version 1.2.  
**Environment configuration:** Pending.  
**Credentials:** Pending deployment configuration.  
**Workflow deployment:** Pending.  
**Integration verification:** Pending.  
**Security verification:** Pending.  
**Production activation:** Not approved.

All deployment and verification statements must reflect actual observed results.
