# ZUNPY Lead Management Automation
## Document 10 — Security and Privacy Considerations

**Version:** 1.2  
**Status:** Security requirements defined; implementation and verification pending  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose and Scope

This document defines the security and privacy requirements for ZUNPY Lead Management Automation.

The system processes business lead information through n8n, Google Sheets, Gmail, forms, webhooks, and REST API integrations.

Its security approach is based on:

- Data minimization.
- Restricted access.
- Secure credential management.
- Protection of public entry points.
- Controlled handling of personal information.
- Safe workflow execution and error logging.
- Responsible retention and deletion.

These requirements describe the intended design. They do not constitute proof of implementation or legal compliance certification.

## 2. Data Classification

The system stores information that may identify individuals or business contacts.

The four Google Sheets worksheets must all be treated as potentially containing personal or confidential business information.

| Worksheet | Information | Security consideration |
|---|---|---|
| `Leads` | Names, contact details, company information, lead status and follow-up dates | Personal and business contact data |
| `Activity_Log` | Lead identifiers, actions, timestamps and activity sources | May reveal customer interactions |
| `Error_Log` | Error categories, timestamps, workflow context and diagnostic details | May contain sensitive operational context |
| `Review_Queue` | Lead identifiers, conflict details and resolution notes | May contain personal and business information |

Access to these worksheets must be restricted to authorized users.

## 3. Data Minimization

Only information necessary for lead management should be collected and stored.

The system should:

- Require a first name and at least one valid contact method.
- Keep optional fields optional.
- Discard an invalid email when a valid phone number remains available.
- Reject submissions without a valid contact method.
- Avoid collecting sensitive personal information.
- Avoid copying unnecessary customer information into activity or error logs.
- Keep conflict review notes concise and relevant.

Portfolio demonstrations must use synthetic or anonymized data.

Real customer records must never be included in public screenshots, examples, exported workflows, or GitHub repositories.

## 4. Authentication and Access Control

### 4.1 n8n Access

The n8n administration interface must not be exposed publicly without appropriate authentication and transport security.

Administrative access should be limited to authorized operators.

Internal forms and operational endpoints must be protected against unauthorized access.

### 4.2 Google Sheets Access

Google credentials must use the minimum permissions required for the workflow.

Access to the CRM spreadsheet must be limited to the owner and explicitly authorized collaborators.

Public sharing of the CRM spreadsheet is not permitted.

### 4.3 Gmail Access

The Gmail credential must be configured for the minimum required sending permissions.

The system must not request or store a user's Gmail password directly in workflow nodes or configuration files.

## 5. Credential and Secret Management

Credentials must be stored using n8n's credential management facilities or another approved secure secret-management mechanism.

The following must never be committed to GitHub:

- Google access tokens.
- OAuth client secrets.
- Gmail credentials.
- API keys.
- Webhook authentication secrets.
- Private keys.
- `.env` files containing secrets.
- Real customer data or private exports.

Workflow exports must be reviewed before publication.

Credential references and configuration examples must use placeholders rather than real values.

If a secret is exposed:

1. Revoke or rotate the affected credential.
2. Review relevant access and activity where possible.
3. Remove the exposed value from active configuration.
4. Review repository history and published artifacts.
5. Document the incident and corrective action.

Deleting a secret from the latest Git commit alone does not guarantee its removal from repository history.

## 6. Public Forms, Webhooks and API Protection

Public registration forms, webhooks, and REST API endpoints are potential entry points for abuse.

The deployment must apply appropriate protections, including:

- HTTPS for externally accessible endpoints.
- Input validation and normalization.
- Authentication for private webhooks and API endpoints.
- Access restrictions for internal forms.
- Appropriate request-size limits.
- Rate limiting or equivalent abuse controls where supported.
- Avoiding unnecessary disclosure of internal workflow details in responses.

Public forms must expose only the fields needed for lead registration.

Internal forms and administrative operations must not be treated as public endpoints.

Webhook and API authentication requirements must be documented for each deployed integration.

## 7. Workflow and CRM Data Integrity

CRM write operations are centralized in WF-03 to reduce conflicting updates.

The implementation must verify the configured execution and serialization behavior under concurrent requests.

Google Sheets does not provide full transactional guarantees.

Search-before-insert is not a guarantee of uniqueness, and concurrent requests may still produce integrity issues.

The system must therefore:

- Validate incoming data before CRM writes.
- Use the defined duplicate detection rules.
- Send conflicting matches to manual review.
- Avoid automatic record merging.
- Record relevant operations in `Activity_Log`.
- Record technical failures in `Error_Log`.

Business conflicts and validation rejections must not be incorrectly classified as technical errors.

## 8. Review Queue and Operational Logs

`Review_Queue` must contain only the information needed to identify and resolve a conflict.

Resolution notes must not contain passwords, tokens, or unrelated personal information.

`Activity_Log` should record operational events without unnecessarily duplicating full lead records.

`Error_Log` should capture enough information to diagnose failures while avoiding:

- Authentication headers.
- Access tokens.
- API secrets.
- Full document contents.
- Unnecessary customer contact information.

Diagnostic messages received from external services must be reviewed before being stored or exposed to users.

## 9. Email and Notification Privacy

Email notifications may contain personal or business contact information.

The system should:

- Send messages only to configured recipients.
- Avoid exposing one lead's information to another lead.
- Use appropriate recipient fields.
- Keep acknowledgement emails limited to relevant confirmation information.
- Avoid including unnecessary internal workflow details.
- Record notification outcomes without storing full message contents unnecessarily.

An automated acknowledgement is an operational confirmation. It is not marketing consent and must not be treated as authorization for unrelated promotional communications.

A notification delivery failure must not undo a successful CRM registration.

The system must not claim exactly-once email delivery. Gmail delivery and Google Sheets notification timestamp recording are separate operations, and partial failures may leave an uncertain notification state.

## 10. Follow-up Data Protection

Follow-up dates and statuses are part of the lead record and must receive the same access protection as other CRM data.

The system should:

- Restrict follow-up management to authorized users.
- Record creation, rescheduling, completion, and cancellation events.
- Avoid exposing follow-up information in public endpoints.
- Notify only the configured owner.
- Exclude leads marked `Won` or `Lost` from scheduled follow-up notifications.

Rescheduling clears `last_follow_up_notification_at` and records `FOLLOW_UP_RESCHEDULED`.

The implementation must preserve the documented behavior while accounting for the lack of transactional guarantees between Gmail and Google Sheets.

## 11. Data Retention and Deletion

A retention policy must be defined by the system owner before production use.

It must cover all four worksheets:

- `Leads`
- `Activity_Log`
- `Error_Log`
- `Review_Queue`

The policy should specify:

- How long active lead records are retained.
- When inactive or closed leads may be archived or deleted.
- How long activity and error records are retained.
- When resolved or ignored review items may be removed.
- How deletion requests are handled.
- Whether backups contain the affected information and how those backups expire.

Deleting a lead from `Leads` alone may leave related information in activity logs, error records, review items, or backups.

Deletion procedures must therefore consider related records and retained copies.

Retention periods and deletion procedures remain deployment decisions until explicitly configured and verified.

## 12. Backups and Recovery

The owner should maintain appropriate backups of the CRM spreadsheet and relevant n8n configuration.

Backups must be stored in an access-controlled location.

Backup handling must follow the same confidentiality requirements as the original data.

Recovery procedures should be tested before production use.

Workflow exports intended for backup or GitHub publication must be sanitized.

## 13. GitHub and Portfolio Publication

The public repository is intended to demonstrate the automation design and implementation without exposing operational data.

Before publishing or updating the repository, review:

- Workflow JSON exports.
- Screenshots.
- README examples.
- Configuration files.
- Git commit history.
- Test data and execution examples.

The repository must not contain:

- Real customer information.
- Spreadsheet IDs or private document links.
- Credentials or tokens.
- Private webhook URLs or secrets.
- Internal operational logs.
- Unredacted screenshots of connected accounts.

Use placeholders such as `YOUR_SPREADSHEET_ID` and synthetic examples.

A sanitized workflow export must be checked before every publication.

## 14. Privacy and Compliance Limitations

This document defines technical and operational safeguards. It does not certify compliance with GDPR, or any other privacy or data-protection legislation.

Before using the system with real customer information, the owner must determine the applicable legal obligations, including:

- Appropriate lawful basis for processing.
- Privacy information provided to leads.
- Data subject rights and request handling.
- Data retention and deletion obligations.
- Processor and third-party service arrangements.
- International data transfers, where applicable.
- Security incident and breach response obligations.

The owner is responsible for assessing these requirements and obtaining professional advice where necessary.

## 15. Production Security Checklist

Before production use, verify the following:

- [ ] n8n administrative access is protected.
- [ ] Internal forms are restricted to authorized users.
- [ ] Public endpoints use HTTPS.
- [ ] Webhook and API authentication is configured where required.
- [ ] Google Sheets access is restricted.
- [ ] Gmail permissions are limited to operational needs.
- [ ] Credentials are stored securely in n8n.
- [ ] No secrets or real customer data are present in GitHub.
- [ ] Workflow exports and screenshots have been reviewed.
- [ ] Error and activity logs avoid unnecessary personal data.
- [ ] Retention and deletion policies are defined.
- [ ] Backup and recovery procedures are documented.
- [ ] Notification failure behavior has been tested.
- [ ] Concurrent CRM writes have been tested.
- [ ] Security and privacy responsibilities are assigned.

## 16. Current Security Status

**Security requirements:** Defined in Version 1.2.  
**Credential configuration:** Pending implementation and verification.  
**Endpoint protection:** Pending deployment verification.  
**Access restrictions:** Pending implementation and verification.  
**Data retention policy:** Requires owner decision.  
**Backup and recovery:** Pending implementation and testing.  
**GitHub sanitization:** Must be checked before publication.  
**Legal compliance assessment:** Owner responsibility.

This document describes the security and privacy requirements for Version 1. It must be reviewed against the actual deployment before the system processes real customer information.
