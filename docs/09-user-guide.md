# ZUNPY Lead Management Automation
## Document 09 — User Guide

**Version:** 1.2  
**Status:** User guide defined; implementation and operational verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Introduction

ZUNPY Lead Management Automation provides a simple way to capture, organize, and follow up on business leads.

The system centralizes lead information in Google Sheets and automates repetitive tasks using n8n.

Version 1 supports:

- Automated lead registration.
- Manual lead registration.
- Duplicate detection.
- Manual review of conflicting records.
- Lead status management.
- Email notifications.
- Follow-up scheduling.
- Activity history.
- Basic reporting.

This guide describes the intended user experience. Features remain subject to implementation and verification.

## 2. Accessing the System

The system provides two lead registration forms:

- A public form for external enquiries.
- An internal form for authorized users.

The public form is intended for potential customers.

The internal form is intended for authorized users who need to register leads manually.

Additional lead registrations may enter the system through configured webhooks or REST API integrations.

The actual form URLs and access instructions will be provided after deployment.

## 3. Registering a New Lead

### 3.1 Public Registration

To register a lead through the public form:

1. Open the public registration form.
2. Enter the lead's first name.
3. Provide an email address, a phone number, or both.
4. Complete any optional fields.
5. Submit the form.

The system validates the information before attempting to create or update a CRM record.

### 3.2 Manual Registration

Authorized users may register leads through the internal form.

The same validation and duplicate detection rules apply.

Manual registrations are identified with source `MANUAL`.

A manual registration triggers an owner notification but does not send an automatic acknowledgement email to the lead by default.

### 3.3 Required Information

The first name is mandatory.

At least one valid contact method must be provided:

- Email address.
- Phone number.

Company, last name, and message are optional.

If an invalid email is submitted together with a valid phone number, the invalid email is discarded and the registration may continue.

If neither email nor phone is valid, the submission is rejected.

## 4. Understanding Lead Registration Results

After submission, the system may produce one of the following outcomes:

| Outcome | Meaning |
|---|---|
| New lead created | A new CRM record has been created |
| Existing lead updated | An existing matching record has been updated |
| Manual review required | Conflicting duplicate matches require owner attention |
| Rejected | The submission does not satisfy validation requirements |
| Technical failure | An operational or integration error prevented processing |

A validation rejection does not create an incomplete lead record.

A technical failure is recorded separately from a business-data conflict.

## 5. Managing Duplicate Leads

The system checks normalized email addresses first and phone numbers as a secondary matching criterion.

### 5.1 Existing Lead Match

When an incoming lead matches an existing record, the system updates that record where appropriate.

Existing valid information is preserved when incoming information is empty or invalid.

The system does not create a second lead merely because the same person submits another enquiry.

### 5.2 Conflicting Matches

A conflict occurs when the submitted email identifies one lead and the submitted phone identifies a different lead.

In this situation:

- Neither existing lead is automatically updated.
- No automatic record merging takes place.
- A review item is created in `Review_Queue`.
- The owner receives a manual review notification.

### 5.3 Resolving a Review Item

An authorized owner reviews the relevant records and chooses an appropriate outcome:

1. Correct the relevant data and resolve the review.
2. Keep both leads separate and resolve the review.
3. Ignore the case.

The selected outcome and explanation must be recorded in `resolution_notes`.

Review statuses are:

- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`
- `IGNORED`

Version 1 does not provide automatic record merging.

## 6. Managing Lead Status

Each lead has a status representing its current business situation.

Allowed statuses:

| Status | Meaning |
|---|---|
| `New` | Newly registered lead |
| `Contacted` | Initial contact has been made |
| `Qualified` | Lead has been assessed as a potential opportunity |
| `Proposal Sent` | A proposal has been sent |
| `Won` | Opportunity successfully closed |
| `Lost` | Opportunity closed without success |

Version 1 validates allowed status values but does not enforce a rigid transition sequence.

Authorized users must update lead status through the configured and approved CRM update method.

The specific operational mechanism for status updates must be established during implementation and deployment. It must not be assumed that a separate user interface exists.

Relevant status changes are recorded in `Activity_Log`.

Leads marked `Won` or `Lost` are excluded from scheduled follow-up notifications.

## 7. Managing Follow-ups

The system supports one active follow-up per lead.

Follow-up information is stored in:

- `follow_up_date`
- `follow_up_status`
- `last_follow_up_notification_at`

### 7.1 Creating a Follow-up

When an authorized user schedules a follow-up:

1. Select the relevant lead.
2. Set the follow-up date using the configured CRM update method.
3. The system sets the follow-up status to `PENDING`.
4. The creation event is recorded.

If no follow-up date exists, the related follow-up fields remain empty.

### 7.2 Rescheduling a Follow-up

If a lead already has an active follow-up, changing its date reschedules the existing follow-up instead of creating a second one.

When rescheduling:

- The previous date is replaced.
- The status remains or becomes `PENDING`.
- `last_follow_up_notification_at` is cleared.
- `FOLLOW_UP_RESCHEDULED` is recorded.

Clearing the notification timestamp allows the newly scheduled date to be processed independently.

### 7.3 Completing a Follow-up

After the follow-up has been handled:

- Set `follow_up_status` to `COMPLETED`.
- Record the completion event.

Completed follow-ups are excluded from future scheduler notifications.

### 7.4 Cancelling a Follow-up

If the follow-up is no longer necessary:

- Set `follow_up_status` to `CANCELLED`.
- Record the cancellation event.

Cancelled follow-ups are excluded from future scheduler notifications.

### 7.5 Follow-up Notifications

The scheduler checks pending follow-ups and notifies the configured owner when a follow-up becomes due.

By default, one successfully recorded notification is allowed per due follow-up.

Additional reminders are not sent unless an explicit policy is configured.

A lead marked `Won` or `Lost` does not receive further scheduled follow-up notifications.

Gmail delivery and Google Sheets timestamp recording are separate operations. In an exceptional partial-failure scenario, a notification may have been delivered without its timestamp being recorded. Exactly-once delivery cannot be guaranteed.

## 8. Email Notifications

The notification policy is:

| Event | Owner notification | Lead acknowledgement |
|---|---|---|
| New automated lead | Yes | Yes, if valid email exists |
| New manual lead | Yes | No, by default |
| Existing lead update | No, by default | No, by default |
| Duplicate conflict | Yes | No |
| Due follow-up | Yes | Not included in Version 1 |
| Critical technical error | Yes, when configured | No |

An email delivery failure does not undo a successful lead registration.

The system records technical email failures for later review.

## 9. Activity History

The `Activity_Log` worksheet provides a chronological record of relevant operations.

Supported events include:

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

Activity sources are:

- `SYSTEM`
- `MANUAL`
- `AUTOMATED`

These values identify the origin of an activity and are different from the lead input source.

## 10. Understanding Technical Errors

Technical errors are recorded in `Error_Log`.

Supported categories:

- `CRM_READ_ERROR`
- `CRM_WRITE_ERROR`
- `EMAIL_ERROR`
- `WORKFLOW_ERROR`

Validation rejections and duplicate conflicts are not technical errors.

An authorized user or administrator should review technical errors and their resolution status.

Error records must not expose credentials, authentication tokens, or unnecessary personal information.

## 11. Basic Reporting

The system provides the following basic metrics:

- Total number of leads.
- Number of new leads.
- Leads grouped by status.
- Leads grouped by source.
- Pending follow-ups.
- Won and Lost opportunities.
- Lead conversion rate.

The conversion rate is calculated as:

`Won / (Won + Lost) * 100`

If there are no closed opportunities, the conversion rate is displayed as `N/A`.

## 12. Data and Timezone Handling

Timestamps are stored in UTC using ISO 8601 format.

The demonstration environment uses `Europe/Madrid` as its local timezone.

Follow-up dates entered in local time are converted to UTC before storage.

Users should interpret displayed dates using the configured deployment timezone.

## 13. User Responsibilities

Authorized users are responsible for:

- Providing accurate lead information.
- Reviewing duplicate conflicts.
- Keeping lead statuses current.
- Scheduling and updating follow-ups.
- Completing or cancelling follow-ups when appropriate.
- Reviewing relevant technical errors.
- Protecting access to CRM data.

Users must not publish real customer information in public project demonstrations or portfolio material.

## 14. Current User Guide Status

**User guide:** Defined and updated in Version 1.2.  
**Public registration:** Pending implementation and verification.  
**Manual registration:** Pending implementation and verification.  
**Status update mechanism:** To be established during implementation.  
**Follow-up management mechanism:** To be established during implementation.  
**Notifications:** Pending implementation and verification.  
**Reporting:** Pending implementation and verification.

This guide describes the intended Version 1 behavior. It must be checked against the actual implementation before being presented as an operational user manual.
