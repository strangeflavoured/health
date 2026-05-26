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

## Continuity and Bus Factor

This is a single-maintainer personal project; the bus factor is **1**. This is a
conscious trade-off appropriate to the project's scope, not an oversight, and it
is recorded as an accepted risk in the
[Threat Model](https://github.com/strangeflavoured/health/blob/main/docs/source/threat-model.md).

Continuity of access does not depend on any single running system. The root of
trust for all local secrets is the GPG key protecting the `pass` store; an
offline, encrypted backup of that private key exists so the secret store can be
reconstructed on a new host if the primary machine is lost. Redis certificates
and ACL credentials are regenerated from documented procedures (see
[Getting Started](https://github.com/strangeflavoured/health/blob/main/docs/source/getting-started.md) and
[Secrets Management with `pass`](https://github.com/strangeflavoured/health/blob/main/docs/source/pass-secrets.md)), so no secret is
irrecoverable as long as the GPG key survives.

Project artefacts that are not local — source history, releases, CI
configuration, and the security policy — live in the GitHub repository and are
not dependent on the maintainer's machine.
