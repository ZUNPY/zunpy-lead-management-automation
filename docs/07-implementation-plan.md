# ZUNPY Lead Management Automation
## Document 07 — Implementation Plan

**Version:** 1.2  
**Status:** Implementation plan defined; development not started  
**Project:** ZUNPY Lead Management Automation

---

## 1. Purpose

This document defines the implementation phases, tasks, dependencies, and completion criteria for ZUNPY Lead Management Automation.

The project will be implemented incrementally, with each phase producing a verifiable result before proceeding to the next major stage.

The implementation must follow the requirements, architecture, workflow design, data model, and testing strategy defined in the project documentation.

## 2. Implementation Principles

The implementation shall follow these principles:

- Keep Version 1 small and focused.
- Use n8n as the workflow automation platform.
- Use Google Sheets as the initial CRM data store.
- Use Gmail for operational notifications.
- Centralize lead creation and update operations through WF-03.
- Reuse a common processing path for all lead input channels.
- Preserve existing valid data.
- Avoid automatic merging of conflicting lead records.
- Test concurrency and document storage limitations.
- Keep credentials and sensitive information out of public exports.
- Verify each phase before treating it as complete.

The initial implementation shall not require additional paid services.

## 3. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Workflow automation | n8n | Workflow orchestration |
| CRM data storage | Google Sheets | Lead and operational records |
| Email integration | Gmail | Owner notifications and acknowledgements |
| Lead input | n8n Forms | Public and internal registration |
| External integration | Webhooks and REST APIs | Automated lead intake |
| Optional scripting | Python | Additional processing only when justified |
| Version control | GitHub | Source code, documentation, and sanitized workflow exports |

## 4. Implementation Phases

### Phase 1 — Environment Setup

**Objective:** Prepare the development environment.

Tasks:

- Install or configure n8n.
- Verify access to the n8n editor.
- Configure the required Google account integration.
- Configure Gmail credentials.
- Create the project directory.
- Establish the GitHub repository structure.
- Define the development and test configuration.
- Configure the demonstration timezone as `Europe/Madrid`.

Acceptance criteria:

- n8n is accessible.
- Required credentials can be configured securely.
- The development environment is documented.
- No secrets are stored in project source files.

**Dependency:** None.

### Phase 2 — CRM Data Model

**Objective:** Create the Google Sheets data structure.

Tasks:

- Create the Google Sheets document.
- Create the `Leads` worksheet.
- Create the `Activity_Log` worksheet.
- Create the `Error_Log` worksheet.
- Create the `Review_Queue` worksheet.
- Add the fields defined in Document 05.
- Define the permitted source, status, event, and review values.
- Prepare synthetic test records.

Acceptance criteria:

- All four worksheets exist.
- Column names match Document 05.
- The data structure supports lead records, activities, errors, reviews, and follow-ups.
- Test records use synthetic data.

**Dependency:** Phase 1.

### Phase 3 — Lead Registration and Validation

**Objective:** Implement lead intake through the supported input channels.

Tasks:

- Create the public n8n lead registration form.
- Create the internal manual registration form.
- Create the webhook input endpoint.
- Define the compatible REST API input structure.
- Implement WF-01 Lead Intake.
- Implement WF-02 Lead Validation.
- Normalize email addresses and phone numbers.
- Validate required fields.
- Enforce the valid contact method rule.
- Discard invalid optional email addresses when a valid phone remains.
- Reject submissions without any valid contact method.
- Implement basic technical error recording.
- Pass validated payloads to the CRM processing workflow.

Acceptance criteria:

- All supported input channels use the common processing path.
- Lead source values are assigned correctly.
- Validation rules behave as specified.
- Invalid submissions are rejected without creating incomplete CRM records.
- Basic technical failures can be recorded.

**Dependency:** Phase 2.

### Phase 4 — Duplicate Prevention and CRM Integrity

**Objective:** Implement centralized CRM operations and controlled duplicate handling.

Tasks:

- Implement WF-03 CRM Operations.
- Centralize all lead creation and update operations.
- Implement normalized email matching.
- Implement normalized phone matching.
- Handle matching email and phone results that identify the same lead.
- Handle email and phone results that identify different leads.
- Preserve existing valid information.
- Create review records in `Review_Queue` for conflicting matches.
- Record duplicate and review events in `Activity_Log`.
- Implement manual review status and resolution recording.
- Define the CRM operation response contract.
- Configure controlled, serialized CRM execution using the actual n8n configuration.
- Test sequential and overlapping CRM submissions.
- Document any remaining Google Sheets concurrency limitations.

Acceptance criteria:

- WF-03 is the only workflow authorized to create or update lead records.
- Matching leads are identified and updated according to the defined rules.
- Conflicting matches are routed for manual review without automatic merging or updating either matched record.
- Review outcomes can be recorded.
- Existing valid data is preserved.
- CRM write serialization is demonstrated or its limitations are documented.
- Search-before-insert is not treated as proof of concurrency safety.

**Dependency:** Phase 3.

### Phase 5 — Email Notifications

**Objective:** Implement operational email notifications.

Tasks:

- Implement WF-04 Email Notifications.
- Configure the owner notification recipient.
- Create the new automated lead notification.
- Create the lead acknowledgement email.
- Implement the manual registration notification policy.
- Implement the duplicate conflict review notification.
- Ensure existing lead updates do not trigger notifications by default.
- Handle email delivery failures.
- Record successful email events.
- Route technical notification failures to WF-06.

Acceptance criteria:

- Owner notifications follow the defined notification matrix.
- Automated lead acknowledgements are sent only when appropriate.
- Manual leads do not receive automatic acknowledgements by default.
- Duplicate conflicts do not trigger lead acknowledgements.
- Email failures do not undo successful CRM registration.
- Notification failures are recorded correctly.

**Dependency:** Phase 4.

### Phase 6 — Follow-up Management

**Objective:** Implement the follow-up lifecycle and scheduled notifications.

Tasks:

- Implement follow-up creation.
- Enforce one active follow-up per lead.
- Implement follow-up rescheduling.
- Reset `last_follow_up_notification_at` when a follow-up is rescheduled.
- Record `FOLLOW_UP_CREATED`.
- Record `FOLLOW_UP_RESCHEDULED`.
- Implement follow-up completion and cancellation.
- Record `FOLLOW_UP_COMPLETED` and `FOLLOW_UP_CANCELLED`.
- Implement WF-05 Follow-up Scheduler.
- Configure UTC timestamp storage and local timezone interpretation.
- Exclude completed and cancelled follow-ups.
- Exclude leads with status `Won` or `Lost`.
- Implement the notification guard.
- Update the notification timestamp only after successful email delivery and successful recording.
- Test repeated scheduler executions.
- Test email delivery followed by a failed Google Sheets timestamp update.
- Document the limitations of exactly-once notification delivery.

Acceptance criteria:

- A new follow-up starts with status `PENDING`.
- Rescheduling updates the existing follow-up rather than creating a second active one.
- Rescheduling clears the previous notification timestamp.
- Completed and cancelled follow-ups are excluded from future notifications.
- Won and Lost leads are excluded.
- Repeated scheduler executions do not resend successfully recorded notifications under normal operating conditions.
- Partial notification failures are identified and documented.

**Dependency:** Phase 5.

### Phase 7 — Centralized Error Handling and Recovery

**Objective:** Complete the technical error handling process.

Tasks:

- Implement WF-06 Error Handling.
- Define the supported technical error categories.
- Record CRM read and write errors.
- Record email delivery errors.
- Record general workflow errors.
- Sanitize error messages.
- Include execution and lead references when available.
- Configure owner notifications for critical errors when appropriate.
- Define error resolution tracking.
- Verify that validation rejections and duplicate conflicts are not classified as technical errors.

Acceptance criteria:

- Technical errors are recorded in `Error_Log`.
- Error categories match Document 05.
- Sensitive information is not exposed in logs.
- Business-rule outcomes remain separate from technical errors.
- Critical error notifications work when configured.

**Dependencies:** Phases 3, 4, 5, and 6.

### Phase 8 — Basic Reporting

**Objective:** Provide an overview of lead activity and follow-up status.

Tasks:

- Implement total lead count.
- Implement lead counts by status.
- Implement lead counts by source.
- Display pending follow-ups.
- Display Won and Lost counts.
- Implement the conversion rate calculation.
- Display `N/A` when there are no closed opportunities.

Acceptance criteria:

- All required metrics are available.
- Reporting results match the underlying Google Sheets data.
- The conversion rate uses `Won / (Won + Lost) * 100`.

**Dependency:** Phase 2, with completed lead, status, and follow-up processing from Phases 3–6.

### Phase 9 — Quality Assurance

**Objective:** Verify the complete implementation against the project requirements.

Tasks:

- Execute the functional test cases in Document 06.
- Execute the integration tests.
- Test all supported lead input channels.
- Test duplicate detection and conflict resolution.
- Test notification rules.
- Test follow-up creation, rescheduling, completion, and cancellation.
- Test notification failure scenarios.
- Execute sequential and simultaneous CRM submission tests.
- Verify actual CRM write serialization behavior.
- Verify timezone handling.
- Verify reporting calculations.
- Execute security and privacy checks.
- Record test results and supporting evidence.
- Document unresolved limitations and failures.

Acceptance criteria:

- Applicable functional tests have been executed.
- Critical acceptance criteria pass.
- Concurrency behavior is demonstrated or explicitly documented.
- Notification failure behavior is tested and documented.
- No unresolved critical failure is concealed or represented as successful.
- Test evidence is retained using synthetic data.

**Dependencies:** Phases 3–8.

### Phase 10 — Documentation and Portfolio Publication

**Objective:** Prepare the project for reproducible demonstration and portfolio publication.

Tasks:

- Finalize project documentation.
- Export the n8n workflows.
- Remove private credentials and configuration data from exports.
- Replace personal Google Sheets identifiers with placeholders.
- Review the GitHub repository contents.
- Add sanitized screenshots and test evidence.
- Write the project README.
- Document setup and configuration steps.
- Document known limitations.
- Publish the approved project materials to GitHub.

Acceptance criteria:

- Documentation matches the implemented and verified behavior.
- Workflow exports contain no credentials or private identifiers.
- A third party can understand the architecture and reproduce the setup using the instructions.
- Screenshots and evidence contain no real personal information.
- The GitHub repository is ready for public portfolio use.

**Dependencies:** Phases 1–9.

## 5. Phase Dependencies

The intended implementation sequence is:

| Phase | Depends on |
|---|---|
| 1. Environment Setup | None |
| 2. CRM Data Model | Phase 1 |
| 3. Lead Registration and Validation | Phase 2 |
| 4. Duplicate Prevention and CRM Integrity | Phase 3 |
| 5. Email Notifications | Phase 4 |
| 6. Follow-up Management | Phase 5 |
| 7. Centralized Error Handling and Recovery | Phases 3–6 |
| 8. Basic Reporting | Phases 2–6 |
| 9. Quality Assurance | Phases 3–8 |
| 10. Documentation and Portfolio Publication | Phases 1–9 |

## 6. Scope Control

The following items are explicitly excluded from Version 1:

- Full CRM functionality.
- Advanced sales pipeline automation.
- Marketing campaigns.
- Multiple active follow-ups per lead.
- Automatic merging of conflicting lead records.
- Advanced analytics and forecasting.
- Mandatory paid integrations.
- Complex role-based permissions.
- Database migration unless required by demonstrated data-integrity limitations.

Any additional feature must be evaluated separately before being included.

## 7. Risk Management

| Risk | Mitigation |
|---|---|
| Duplicate records from concurrent submissions | Centralized CRM writer, serialization verification, and concurrency tests |
| Google Sheets integrity limitations | Document limitations and consider transactional storage only if necessary |
| Incorrect lead data | Common validation and normalization |
| Accidental data overwrites | Preserve existing valid information |
| Email delivery failures | Centralized error recording and separate CRM operations |
| Repeated follow-up notifications | Notification guard and timestamp tracking |
| Partial failure after email delivery | Dedicated failure tests and documented exactly-once limitation |
| Exposure of credentials or personal data | Secure credentials and sanitized public exports |
| Scope expansion | Explicit Version 1 exclusions |

## 8. Project Completion Criteria

The project shall be considered complete for portfolio publication when:

- All ten implementation phases have been completed.
- The documented workflows match the actual implementation.
- Functional and integration tests have been executed.
- Critical failures have been resolved or explicitly disclosed.
- Concurrency and notification limitations have been tested and documented.
- Security and privacy checks have been completed.
- Reproducible setup instructions are available.
- Sanitized workflow exports and evidence are ready for publication.

Implementation completion, QA approval, and production readiness must be treated as separate milestones.

## 9. Current Project Status

**Implementation plan:** Defined and updated in Version 1.2.  
**Environment setup:** Pending.  
**Development:** Not started.  
**Testing:** Pending implementation.  
**Portfolio publication:** Pending.

No phase shall be marked complete without observable evidence of its acceptance criteria.
