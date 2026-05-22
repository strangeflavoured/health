# Maintainers

## Project Members

| Name     | GitHub            | Role       | Sensitive resource access |
| -------- | ----------------- | ---------- | ------------------------- |
| Jonathan | @strangeflavoured | Maintainer | All (see below)           |

## Sensitive Resources

- GitHub repository settings and branch protection rules
- GitHub Actions secrets (Redis mTLS certificates, passwords, app private key)
- `pass` GPG keystore holding Redis certificates and ACL credentials
- Renovate GitHub App (`deps-bot`)
- bestpractices.dev project entry (project 12933)

## Roles and Responsibilities

**Maintainer** (sole role): responsible for all code review, security decisions,
dependency management, vulnerability triage, and releases. No contributions
are merged without maintainer approval.
