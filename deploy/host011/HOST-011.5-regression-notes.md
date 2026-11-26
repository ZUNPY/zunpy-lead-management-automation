# HOST-011.5 — Regression and recovery

Date: 2026-11-26. Coordinated manual workflow `Qecf6SEhe80O7mOs`, five fixed serial missions, original HOST-010 acceptance workflow untouched.

- Execution 143: error, 7.289 seconds. ACP initialize verified, HTTP 503 from `acp.inference` (`status:blocked`); later stages not reached. Exact cause not available from sanitized bridge response.
- Execution 144: isolated existing inference workflow `lZ7JC4IGb6qK9IjR`, success in 4.482 seconds. Output verified protocol 1, inference true, model configured gemma4:26b, endpoint 127.0.0.1:11434/v1, answer 42, toolEvents 0. No changes to code, configuration, services, or dependencies between attempts.
- Execution 145: one complete coordinated retest initiated after isolated recovery. Status pending at time of writing. No automatic retries configured.

Scope: bounded fixtures, no general shell or project access. The observed isolated success indicates recovery, not a verified root cause or proof of future stability. No HOST-011 freeze until complete retest evidence is obtained.
