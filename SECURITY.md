# Security Policy

## Supported Versions

| Version        | Supported             |
| -------------- | --------------------- |
| `main`         | ✅ Active development |
| Older releases | ❌ No backports       |

Only the current `main` branch receives security fixes. There are no maintained
release branches.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Use GitHub's private vulnerability reporting:

👉 [Report a vulnerability](https://github.com/strangeflavoured/health/security/advisories/new)

This creates a private advisory visible only to the repository owner.
When a security vulnerability is confirmed and a fix is released, a GitHub Security Advisory
will be published at https://github.com/strangeflavoured/health/security/advisories.
The advisory will include a CVE if applicable and a description of the vulnerability,
affected versions, and fix.

## Scope

This repository is a personal health data platform. The following components are
in scope:

- Apple Health export parser and ETL pipeline (`src/`)
- Django REST backend (`backend/`)
- React frontend (`frontend/`)
- Redis TimeSeries storage layer and mTLS configuration (`docker/`)
- CI/CD scripts (`scripts/`)

Out of scope: third-party dependencies (report those to the relevant upstream
project), and the development-only local setup with mock credentials.

## Verifying releases

Each release publishes SHA-256 checksums in `checksums.sha256`. Verify with:

```sh
sha256sum -c checksums.sha256
```

## Support policy

Only the latest release receives security updates.
Older releases are unsupported and will not receive patches.

## Automated Security Scanning

The following tools run continuously in CI and findings are visible in the
[Security tab](https://github.com/strangeflavoured/health/security):

| Tool                                                                                            | What it scans                                           | Schedule                      |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------- |
| [CodeQL](https://github.com/strangeflavoured/health/actions/workflows/codeql.yml)               | Python, JavaScript/TypeScript, Actions workflows (SAST) | Push, PR, weekly              |
| [OSV Scanner](https://github.com/strangeflavoured/health/actions/workflows/osv-scan.yml)        | All dependency manifests (SCA)                          | Push, PR, weekly              |
| [OpenSSF Scorecard](https://github.com/strangeflavoured/health/actions/workflows/scorecard.yml) | Repository security posture                             | Push, PR, weekly              |
| ruff (pre-commit)                                                                               | Python static analysis                                  | Every PR and push             |
| Renovate                                                                                        | Dependency vulnerability alerts                         | Weekly, automerge minor/patch |

All GitHub Actions in this repository are pinned to full commit SHAs.
`GITHUB_TOKEN` permissions are set to read-only at the repository level, with
per-job escalation only where required.
