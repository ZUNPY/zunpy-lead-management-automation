# ZUNPY Lead Management Automation

![ZUNPY Banner](docs/images/zunpy-lead-management-banner.png)

**Project status:** Verified demo / working prototype  
**Version:** Demo v1  
**Category:** Business Process Automation  
**Business contact:** hello@zunpyai.com

## 1. Project Overview

ZUNPY Lead Management Automation is a workflow-based solution designed to help small service businesses capture, validate, organize and follow up with potential customers.

The system reduces repetitive lead-management work, centralizes lead data, prevents duplicate records, logs activity and helps ensure follow-up actions are not forgotten.

The current demo has been tested end to end in a controlled sandbox environment using fictional lead data.

## 2. Problem Statement

Small businesses often receive customer enquiries through different channels but lack a centralized and reliable process to manage them.

This can result in:

- Lost or overlooked enquiries.
- Duplicate customer records.
- Delayed responses.
- Inconsistent follow-up.
- Poor visibility into lead activity.

## 3. Verified Demo Flow

The current ZUNPY demo uses n8n to orchestrate five workflow stages:

1. **Lead Intake** — accepts manual, form, webhook or API lead input.
2. **Lead Validation** — validates and normalizes required contact data.
3. **CRM Operations** — creates or updates leads in Google Sheets and detects duplicate matches.
4. **Email Notifications** — sends controlled Gmail notifications and records the activity.
5. **Follow-up Scheduler** — detects due follow-ups, triggers the notification workflow and marks the follow-up as notified.

```text
Lead Intake
    ↓
Validation
    ↓
CRM Operations
    ↓
Email Notifications
    ↑
Follow-up Scheduler
```

## 4. Verified Capabilities

- Lead intake through multiple supported channels.
- Required-field and contact-data validation.
- Google Sheets CRM integration.
- Duplicate detection and controlled create/update logic.
- Activity logging.
- Real Gmail API notification delivery.
- Follow-up scheduling and notification state tracking.
- Controlled sandbox testing with fictional data.
- SPF, DKIM and DMARC passing on the tested ZUNPY business-email delivery path.

## 5. Target Users

- Small service businesses.
- Freelancers and consultants.
- Independent service providers.
- Small sales and operations teams.

## 6. Technology Stack

| Technology | Purpose |
|---|---|
| n8n | Workflow orchestration |
| Google Sheets | Lead database and lightweight CRM |
| Gmail API | Automated email notifications |
| Webhooks / REST APIs | Automated data intake |
| JavaScript / n8n Code nodes | Validation and workflow logic |
| GitHub | Version control and project documentation |

## 7. Demo Scope

The verified demo focuses on a reusable lead-management workflow using standard integrations.

It includes:

- Lead intake.
- Data validation and normalization.
- Duplicate prevention.
- Centralized lead storage.
- Activity logging.
- Email notifications.
- Follow-up scheduling.

A full custom CRM, large-scale outbound campaigns, advanced analytics, WhatsApp integration, guaranteed conversion results and client-specific production hardening are outside the current demo scope.

## 8. Testing and Verification

The workflow has been tested end to end with fictional lead data in the ZUNPY sandbox.

Verified evidence includes:

- Successful lead intake and validation.
- Successful CRM record creation.
- Successful activity logging.
- Successful real Gmail API notification delivery from the ZUNPY business domain.
- Successful follow-up detection and notification.
- Follow-up state updated to prevent repeated notifications.
- Business-domain email authentication passing SPF, DKIM and DMARC checks on the controlled test.

## 9. Project Status

**Verified demo / working prototype.**

The core workflow has been demonstrated end to end. This repository represents a commercial demonstration and reusable automation foundation, not a claim of universal production readiness.

Client deployment would still require environment-specific configuration, credentials, acceptance testing and any agreed production hardening.

## 10. Security and Privacy

The public demo uses fictional lead information.

Credentials, OAuth secrets, API keys, private customer data and personal information must never be committed to the repository.

## About ZUNPY

ZUNPY builds practical automation solutions using n8n, Python, APIs and AI-assisted workflows.

The focus is on reducing repetitive business work with solutions that are understandable, maintainable and testable.

**Contact:** hello@zunpyai.com

---

*Built and verified as a practical automation project by ZUNPY.*
