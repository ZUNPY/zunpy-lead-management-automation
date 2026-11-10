# ZUNPY Lead Management Automation
## Document 05 — Data Model

**Version:** 1.4  
**Status:** Data model defined; implementation and verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose

This document defines the data structure used by ZUNPY Lead Management Automation.

The system uses one Google Sheets document with four worksheets:

1. `Leads`
2. `Activity_Log`
3. `Error_Log`
4. `Review_Queue`

The model supports lead registration, duplicate detection, activity tracking, technical error logging, manual conflict resolution, and follow-up management.

All CRM lead creation and update operations shall be centralized through WF-03.

## 2. General Data Rules

- Each lead must have a unique `lead_id`.
- Timestamps must be stored in UTC using ISO 8601 format.
- The default demonstration timezone is `Europe/Madrid`.
- Email addresses must be normalized to lowercase.
- Phone numbers must be normalized without inventing country codes.
- Empty or invalid incoming values must not overwrite existing valid information.
- The lead input source and activity source are separate concepts.
- CRM write operations must be serialized where supported by the actual n8n configuration.
- Google Sheets does not provide transactional uniqueness guarantees.

## 3. Worksheet 1 — Leads

### 3.1 Purpose

Stores the main lead records and their current CRM information.

### 3.2 Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `lead_id` | String | Yes | Unique lead identifier |
| `first_name` | String | Yes | Lead first name |
| `last_name` | String | No | Lead last name |
| `email` | String | Conditional | Valid normalized email address |
| `phone` | String | Conditional | Valid normalized phone number |
| `company` | String | No | Company or organization |
| `source` | String | Yes | Original lead input source |
| `message` | String | No | Original enquiry or message |
| `status` | String | Yes | Current lead status |
| `created_at` | DateTime | Yes | Creation timestamp in UTC |
| `updated_at` | DateTime | Yes | Last update timestamp in UTC |
| `follow_up_date` | DateTime | No | Scheduled follow-up date/time in UTC (ISO 8601 with 'Z' indicator) |
| `follow_up_status` | String | Conditional | Follow-up lifecycle status |
| `last_follow_up_notification_at` | DateTime | No | Timestamp of the last successfully recorded follow-up notification |
| `notes` | String | No | Internal notes |

### 3.3 Field Rules

**Contact information**

- `first_name` is mandatory.
- At least one valid contact method must be present: `email` or `phone`.
- If an optional email is invalid but a valid phone exists, the invalid email must be discarded.
- An invalid email must never be stored or used for duplicate matching.

**Source**

Allowed values:

- `FORM`
- `WEBHOOK`
- `MANUAL`
- `API`

**Status**

Allowed values:

- `New`
- `Contacted`
- `Qualified`
- `Proposal Sent`
- `Won`
- `Lost`

Version 1 validates allowed status values but does not enforce a rigid transition graph.

**Timestamps**

- `created_at` is assigned when the lead is created.
- `updated_at` changes when relevant lead information is updated.
- Both timestamps use UTC ISO 8601 format.

### 3.4 Follow-up Field Rules

Allowed values for `follow_up_status`:

- `PENDING`
- `COMPLETED`
- `CANCELLED`

Rules:

- `follow_up_date` must be a DateTime value. While user-facing entry and display use the configured local timezone (e.g., `Europe/Madrid`), all local input must be converted to UTC before storage. This applies to both the creation of new follow-ups and the rescheduling of existing ones.
- If `follow_up_date` is empty, `follow_up_status` and `last_follow_up_notification_at` remain empty.
- When a follow-up is created, its initial status is `PENDING`.
- Only one active follow-up is allowed per lead.
- A new follow-up for a lead with an active follow-up reschedules the existing one.
- Rescheduling replaces `follow_up_date`, keeps or sets the status to `PENDING`, and clears `last_follow_up_notification_at`.
- Completing a follow-up changes its status to `COMPLETED`.
- Cancelling a follow-up changes its status to `CANCELLED`.
- Completed and cancelled follow-ups are excluded from future scheduled notifications.
- Leads with status `Won` or `Lost` are excluded from scheduled follow-up notifications.

`last_follow_up_notification_at` is updated only after successful email delivery and successful recording of that delivery.

The field is a notification tracking mechanism, not an absolute guarantee of exactly-once email delivery. Gmail and Google Sheets do not provide a shared atomic transaction.

### 4. Worksheet 2 — Activity_Log

### 4.1 Purpose

Stores a chronological history of relevant lead, CRM, and follow-up events.

### 4.2 Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `activity_id` | String | Yes | Unique activity identifier |
| `lead_id` | String | Conditional | Related lead identifier |
| `event_type` | String | Yes | Type of recorded event |
| `source` | String | Yes | Activity origin |
| `description` | String | No | Short event description |
| `timestamp` | DateTime | Yes | Event timestamp in UTC |
| `execution_id` | String | No | Related n8n execution identifier |

### 4.3 Supported Event Types

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

When an existing lead is matched, the system may record `DUPLICATE_DETECTED` alongside `LEAD_UPDATED`.

`FOLLOW_UP_RESCHEDULED` records a change to an existing active follow-up. It does not represent creation of a second follow-up.

### 4.4 Activity Source Values

- `SYSTEM`
- `MANUAL`
- `AUTOMATED`

These values describe who or what generated the activity.

They must not be confused with the lead input source values stored in `Leads.source`.

### 5. Worksheet 3 — Error_Log

### 5.1 Purpose

Stores technical errors generated by workflow execution or external integrations.

### 5.2 Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `error_id` | String | Yes | Unique error identifier |
| `workflow_name` | String | Yes | Originating workflow |
| `execution_id` | String | No | Related n8n execution identifier |
| `lead_id` | String | No | Related lead identifier, when available |
| `error_category` | String | Yes | Technical error category |
| `error_message` | String | Yes | Sanitized error description |
| `occurred_at` | DateTime | Yes | Error timestamp in UTC |
| `resolution_status` | String | Yes | Error resolution state |

### 5.3 Error Categories

Allowed values:

- `CRM_READ_ERROR`
- `CRM_WRITE_ERROR`
- `EMAIL_ERROR`
- `WORKFLOW_ERROR`

Validation rejections and duplicate conflicts are business outcomes, not technical errors.

They must not be stored as technical failures in `Error_Log`.

Error messages must not contain credentials, authentication tokens, or unnecessary personal information.

### 6. Worksheet 4 — Review_Queue

### 6.1 Purpose

Stores duplicate conflicts requiring manual review.

The worksheet prevents automatic merging or updating when email and phone matching identify different existing leads.

### 6.2 Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `review_id` | String | Yes | Unique review identifier |
| `detected_at` | DateTime | Yes | Conflict detection timestamp in UTC |
| `email_match_lead_id` | String | No | Lead identified by email matching |
| `phone_match_lead_id` | String | No | Lead identified by phone matching |
| `source` | String | Yes | Original lead input source |
| `review_reason` | String | Yes | Explanation of the conflict |
| `review_status` | String | Yes | Current review state |
| `resolution_notes` | String | No | Manual resolution details |

### 6.3 Review Status Values

- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`
- `IGNORED`

### 6.4 Review Resolution Rules

The owner may:

1. Correct relevant data and resolve the review.
2. Keep both records separate and resolve the review.
3. Ignore the case.

The selected outcome must be documented in `resolution_notes`.

Version 1 does not support automatic lead merging.

Review records must contain only the information necessary to investigate and resolve the conflict.

### 7. Data Relationships

The four worksheets are related through identifiers rather than database foreign-key constraints.

- `Leads.lead_id` identifies the main lead record.
- `Activity_Log.lead_id` references the related lead when available.
- `Error_Log.lead_id` references the related lead when available.
- `Review_Queue.email_match_lead_id` and `Review_Queue.phone_match_lead_id` reference the existing leads involved in a conflict.

`review_id`, `error_id`, and `activity_id` are separate identifiers for their respective records.

## 8. Transient Workflow Fields

The following fields are used for inter-workflow communication and operational control:

- `operation_type`
- `operation_status`

These fields are transient and must not be added as columns to any of the four Google Sheets worksheets (`Leads`, `Activity_Log`, `Error_Log`, or `Review_Queue`).

## 9. Data Integrity and Concurrency

Google Sheets is the initial storage solution for Version 1.

To reduce duplicate and conflicting writes:

- All lead creation and update operations must pass through WF-03.
- CRM write operations must be serialized where supported by the actual n8n configuration.
- The implementation must test sequential and simultaneous submissions.
- Search-before-insert must not be treated as sufficient proof of uniqueness.
- Any remaining concurrency limitation must be documented.

If reliable integrity cannot be demonstrated with the initial configuration, a transactional database may be considered in a future version.

## 10. Data Retention and Privacy

- Store only information required for lead management.
- Restrict access to the Google Sheets document.
- Avoid storing sensitive information in activity descriptions or error messages.
- Apply retention and deletion procedures consistently across all four worksheets.
- Ensure backups and exported copies are considered when deleting records.
- Do not publish real lead data in public GitHub examples.

## 11. Current Status

**Data model:** Defined and updated in Version 1.4.  
**Google Sheets implementation:** Pending.  
**Field validation:** Pending implementation and testing.  
**Concurrency verification:** Pending.  
**Privacy and retention controls:** Defined; operational verification pending.
