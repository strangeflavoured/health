# Threat Model

Version: 1.0 | Last reviewed: YYYY-MM-DD

## Scope

This document covers the health data tracking application, including
the web frontend, backend API, and data storage layer.

## Assets

| Asset                        | Sensitivity | Notes                         |
| ---------------------------- | ----------- | ----------------------------- |
| User health records          | Critical    | PHI — must not leak           |
| Auth tokens / sessions       | High        | Compromise = account takeover |
| Aggregated statistics        | Medium      | Less sensitive, no PII        |
| Application config / secrets | High        | DB credentials, API keys      |

## Trust Boundaries

- **Browser ↔ API**: untrusted input from users; all data validated server-side
- **API ↔ Database**: trusted internal network; parameterized queries only
- **API ↔ External services**: (list any: OAuth providers, email, etc.)
- **CI/CD ↔ Repository**: workflows run with least-privilege tokens

## Attack Surface

| Entry Point           | Threat                           | Mitigation                            |
| --------------------- | -------------------------------- | ------------------------------------- |
| Login form            | Brute force, credential stuffing | Rate limiting, MFA                    |
| Data input fields     | Injection (SQL, XSS)             | Input validation, ORM, CSP            |
| File uploads (if any) | Malicious files                  | Type/size validation, sandboxing      |
| API endpoints         | Unauthorized access              | Auth checks on every route            |
| Dependencies          | Supply chain compromise          | Dependabot, pip-audit, SBOM           |
| CI/CD pipelines       | Secret exfiltration              | Scoped tokens, no untrusted PR access |

## Critical Code Paths

1. **Authentication flow** — login, session creation, token validation
2. **Health data write** — input → validation → storage
3. **Health data read** — auth check → query → response
4. **Password reset** — token generation → email delivery → token consumption

## Out of Scope

- Physical access to servers (hosted on GitHub/cloud provider)
- Anthropic/third-party infrastructure

## Known Risks & Accepted Mitigations

| Risk            | Likelihood | Impact | Mitigation               | Status |
| --------------- | ---------- | ------ | ------------------------ | ------ |
| Dependency CVEs | Medium     | Medium | Automated scanning + VEX | Active |
