# ZUNPY Lead Management Automation
## 03 — System Architecture

**Project status:** Planned  
**Version:** 1.1  
**Architecture type:** Modular workflow-based automation  
**Primary platform:** n8n

## 1. Purpose

This document defines the technical architecture of ZUNPY Lead Management Automation.

The system is designed as a lightweight lead management solution for small businesses, freelancers and independent service providers.

The architecture prioritizes:

- Simple deployment.
- Reliable data processing.
- Duplicate prevention.
- Modular workflows.
- Low operating costs.
- Secure integrations.
- Maintainability and future extensibility.

The initial implementation will use n8n, Google Sheets and Gmail.

## 2. Architecture Overview

The system follows a modular architecture consisting of seven layers:

1. Lead Input.
2. Validation and Normalization.
3. Duplicate Detection.
4. Centralized CRM Operations.
5. Data Storage and Review.
6. Communications.
7. Follow-up and Reporting.

All lead registration methods must use the same validation and CRM processing logic.

## 3. System Components

### 3.1 Lead Input Layer

The system supports four input methods:

- Public n8n registration form.
- Internal n8n manual registration form.
- External webhook.
- Compatible REST API integrations.

Both forms and external integrations must submit information to a common processing workflow.

Manual registration must not bypass validation or duplicate detection.

All incoming records must be mapped to a common data structure.

### 3.2 Validation and Normalization Layer

This layer validates incoming information before CRM operations.

Responsibilities:

- Check required fields.
- Verify that at least one valid contact method is supplied.
- Normalize email addresses.
- Normalize phone numbers.
- Validate the registration source.
- Reject malformed input.
- Preserve valid existing information during updates.

Email addresses are trimmed and converted to lowercase.

Phone normalization must use a consistent representation without inventing missing country codes.

### 3.3 Duplicate Detection Layer

The system uses two identifiers:

- Normalized email address: primary matching identifier.
- Normalized phone number: secondary matching identifier.

The processing logic must:

1. Search for an email match when an email is available.
2. Search for a phone match when a phone number is available.
3. Compare the matching records.
4. Update the existing record when the identifiers identify the same lead.
5. Create a new lead when no match exists.
6. Flag conflicting matches for manual review.

If email and phone identify different leads, neither record may be automatically merged or overwritten.

### 3.4 Centralized CRM Operations Layer

All CRM creation and update operations must pass through a centralized CRM processing component.

This component is responsible for:

- Searching existing leads.
- Creating new records.
- Updating existing records.
- Recording activities.
- Managing duplicate conflicts.
- Maintaining data integrity.

No independent workflow should write directly to the `Leads` worksheet.

#### Concurrency Control

Google Sheets does not provide transactional guarantees for this use case.

The implementation must therefore serialize CRM write operations.

The preferred approach is a centralized CRM writer with controlled execution concurrency.

The selected n8n configuration must be verified to ensure that two CRM write operations cannot execute the critical search-and-write sequence simultaneously.

A simple search-before-insert operation is not sufficient to guarantee duplicate prevention.

If safe serialization cannot be demonstrated, the limitation must be documented and an alternative storage mechanism considered.

### 3.5 Data Storage and Review Layer

Google Sheets will provide the initial CRM storage.

The spreadsheet will contain four worksheets:

| Worksheet | Responsibility |
|---|---|
| Leads | Current lead records |
| Activity_Log | History of lead operations |
| Error_Log | Technical failures |
| Review_Queue | Data conflicts requiring human review |

The `Review_Queue` is used for conflicts such as email and phone identifiers matching different leads.

These conflicts are not automatically classified as technical errors.

### 3.6 Communications Layer

Gmail will provide the initial email integration.

The communication component supports:

- Internal notifications.
- Lead acknowledgement emails.
- Follow-up reminders.
- Critical error notifications.

Communication must occur after the relevant CRM operation has succeeded.

Email failures must be handled independently from CRM storage failures.

### 3.7 Follow-up and Reporting Layer

The system will provide basic follow-up management and reporting.

Follow-up responsibilities include:

- Storing a planned follow-up date and time.
- Tracking follow-up status.
- Identifying pending and overdue follow-ups.
- Sending controlled notifications.
- Recording follow-up activities.

The initial version supports one active follow-up per lead.

Reporting will use the CRM records and their associated activity data.

## 4. Spreadsheet Data Architecture

### 4.1 Leads

Stores the current information for each lead.

Each record has a unique `lead_id`.

The worksheet includes contact information, source, status, timestamps, follow-up information and internal notes.

### 4.2 Activity_Log

Stores relevant events throughout the lead lifecycle.

Each activity must include:

- Unique activity identifier.
- Associated lead identifier.
- Activity type.
- Event timestamp.
- Activity source.
- Relevant description.

Activity sources are:

- SYSTEM
- MANUAL
- AUTOMATED

### 4.3 Error_Log

Stores technical processing failures.

Examples include:

- CRM read failures.
- CRM write failures.
- Email delivery failures.
- Unexpected workflow failures.

Error records should contain execution references and avoid unnecessary personal information.

### 4.4 Review_Queue

Stores conflicts requiring manual investigation.

Each review item must include:

- Unique review identifier.
- Detection timestamp.
- Matching lead identifiers.
- Registration source.
- Conflict reason.
- Review status.
- Resolution notes.

A conflict must remain unresolved until an authorized user reviews it.

## 5. Workflow Architecture

The system will use the following logical workflows.

| Workflow | Name | Responsibility |
|---|---|---|
| WF-01 | Lead Intake | Receive public, manual and external submissions |
| WF-02 | Lead Validation | Validate and normalize information |
| WF-03 | CRM Operations | Centralized lookup, creation and updates |
| WF-04 | Email Notifications | Send and record email notifications |
| WF-05 | Follow-up Scheduler | Identify and notify pending follow-ups |
| WF-06 | Error Handling | Centralize technical error management |

The CRM Operations workflow must be the only component responsible for writing lead records.

All input methods must use the same validation and CRM processing path.

## 6. Main Data Flows

### 6.1 New Lead

1. A lead arrives through an authorized input method.
2. The input is mapped to the common data structure.
3. Validation and normalization are performed.
4. Duplicate detection is executed.
5. The CRM Operations component creates the record.
6. The creation activity is recorded.
7. The owner receives an internal notification.
8. An acknowledgement email is sent when appropriate.

### 6.2 Existing Lead

1. A new submission arrives.
2. The information is validated and normalized.
3. Existing records are searched.
4. Matching identifiers are compared.
5. The existing record is updated when appropriate.
6. Empty or invalid values do not overwrite valid information.
7. The update activity is recorded.

Existing lead updates do not trigger acknowledgement emails by default.

### 6.3 Conflicting Identifiers

1. Email and phone matching are performed.
2. Different existing lead identifiers are detected.
3. Automatic merging and updating are stopped.
4. A review item is created in `Review_Queue`.
5. The owner is notified that manual review is required.
6. An authorized user investigates and records the resolution.

### 6.4 Follow-up

1. A scheduled workflow retrieves active leads.
2. Leads with pending follow-ups are identified.
3. Due and overdue items are evaluated.
4. Notification history is checked.
5. Appropriate reminders are sent.
6. Notification activities are recorded.

Completed and cancelled follow-ups are excluded from further reminders.

Won and Lost leads are excluded from active follow-up notifications.

## 7. Notification Rules

| Event | Owner notification | Lead acknowledgement |
|---|---|---|
| New automated lead | Yes | Yes, if valid email |
| New manual lead | Yes | No, by default |
| Existing lead update | No, by default | No |
| Duplicate conflict | Yes, for review | No |
| Due or overdue follow-up | Yes | No |
| Critical workflow error | When configured | No |

All emails must be sent only after the relevant CRM operation has succeeded.

## 8. Error Handling and Reliability

The system must distinguish between:

- Input validation failures.
- Duplicate conflicts.
- CRM read failures.
- CRM write failures.
- Email delivery failures.
- Unexpected workflow failures.

Basic error recording must be implemented from the initial CRM integration phase.

The centralized error management workflow will be introduced in a later implementation phase.

A failed email must not invalidate a successful CRM registration.

A failed CRM write must never be reported as a successful registration.

Retries must be designed to avoid unintended duplicate records.

## 9. Timezone Strategy

All timestamps will be stored in UTC using ISO 8601 format.

The deployment will define a configurable local timezone.

The initial demonstration configuration will use:

`Europe/Madrid`

Follow-up dates and times must be interpreted in the configured timezone and converted consistently for storage and presentation.

## 10. Security Architecture

The architecture follows these principles:

- Credentials are stored using n8n credential management.
- Spreadsheet access is restricted.
- Public webhooks use appropriate protection.
- Input data is validated.
- Error logs minimize personal information.
- Workflow exports are sanitized before publication.
- Test data is fictitious.
- Backup and recovery procedures are documented.

## 11. Scalability and Future Improvements

Google Sheets is suitable for the initial small-scale implementation.

If usage grows or stronger transactional guarantees are required, the storage layer may be migrated to PostgreSQL or another suitable database.

The workflow architecture should minimize dependencies on spreadsheet-specific operations to facilitate future migration.

Other possible future improvements include:

- Multiple follow-ups per lead.
- Advanced CRM interfaces.
- Additional communication channels.
- More advanced reporting.
- Multi-user permission management.

These features are outside the initial version.

## 12. Architecture Acceptance Criteria

The architecture will be considered ready for implementation when:

1. All registration methods use a common processing path.
2. CRM writes are centralized.
3. Duplicate matching rules are defined.
4. Conflicting identifiers have a dedicated review process.
5. The four spreadsheet worksheets are defined.
6. Notification conditions are documented.
7. Follow-up lifecycle rules are defined.
8. Timezone handling is consistent.
9. Error handling responsibilities are separated.
10. Concurrency control has a verifiable implementation strategy.

**Document status:** Architecture defined — implementation and technical verification pending.
