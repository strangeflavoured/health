# Security

This page summarises the security posture of HealthAnalyser and points to the
authoritative documents. The canonical policy lives in
[`SECURITY.md`](https://github.com/strangeflavoured/health/blob/main/SECURITY.md);
this page adds the design rationale and operational detail that supports the
[OpenSSF Best Practices](https://www.bestpractices.dev/projects/12933) criteria.

## Reporting a vulnerability

Do **not** open a public issue for a suspected vulnerability. Use GitHub's
private vulnerability reporting:

- [Report a vulnerability](https://github.com/strangeflavoured/health/security/advisories/new)

This opens a private advisory visible only to the maintainer. Once a fix ships,
a [GitHub Security Advisory](https://github.com/strangeflavoured/health/security/advisories)
is published, including a CVE where applicable.

Only the current `main` branch is supported; there are no maintained release
branches and no backports.

## Data sensitivity

HealthAnalyser processes personal health information (PHI) exported from Apple
Health. Health records are treated as the most sensitive asset in the system and
must never leave the local stack in plaintext. See the
[Threat Model](threat-model.md) for the full asset inventory, trust boundaries,
and accepted risks.

## Transport security and access control (Redis mTLS)

The storage layer is a Redis Stack instance reached only over mutual TLS:

- TLS is mandatory on port `6380`; the non-TLS port is disabled.
- Every client presents a certificate signed by the project's local CA, and the
  server presents its own certificate, so both ends are authenticated.
- Access is partitioned by Redis ACL users with least-privilege command sets.
  The `app` user may write time series under the `HK*` keyspace; the `insight`
  user has read-only query commands; the `healthcheck` user may only `PING`; and
  the `default` user is disabled entirely.

ACL passwords are never stored in plaintext: the ACL file records SHA-256
hashes generated at start-up from the values held in `pass`. See
[Using Redis & Docker](docker-redis.md) and
[Secrets Management with `pass`](pass-secrets.md) for the operational workflow.

## Secrets handling

- Local secrets (certificates, private keys, ACL passwords) live in a
  GPG-backed [`pass`](pass-secrets.md) store and never touch the repository.
- At start-up, `scripts/compose-wrapper.sh` materialises them onto a per-user
  tmpfs at `/dev/shm/health-secrets-$(id -u)` with `0700`/`0400` permissions,
  mounts them into containers as Docker secrets under `/run/secrets`, and wipes
  the tmpfs on `down`.
- No secret is ever passed through a container environment variable; this can be
  verified with `docker exec health-redis env`.
- In CI, the same material is provided through GitHub Actions secrets and
  reconstructed by `scripts/load-ci-secrets.sh` for the integration test only.

## Supply-chain assurance

| Control                  | Implementation                                                                                                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pinned actions           | Every GitHub Action `uses:` is pinned to a full commit SHA with a version comment; mutable tags are rejected in review.                                                      |
| Reproducible Python deps | All requirements are compiled with `pip-compile --generate-hashes` and installed with `pip install --require-hashes`. CI fails if any compiled file lacks `--hash=` entries. |
| Pinned base images       | Dockerfiles pin base images by digest (`@sha256:...`).                                                                                                                       |
| SBOM                     | A CycloneDX SBOM is generated on every release (`anchore/sbom-action`) and attached to the GitHub Release.                                                                   |
| Build provenance         | The docs artifact, SBOM, and VEX document are signed with `actions/attest-build-provenance`.                                                                                 |
| Vulnerability exceptions | Triaged, non-applicable advisories are published as an [OpenVEX](https://github.com/strangeflavoured/health/tree/main/.openvex) document.                                    |
| Release verification     | Releases publish `checksums.sha256`; verify with `sha256sum -c checksums.sha256`.                                                                                            |

## Automated scanning

The following run continuously; findings surface in the repository
[Security tab](https://github.com/strangeflavoured/health/security).

| Tool                  | Scope                                            | Schedule          |
| --------------------- | ------------------------------------------------ | ----------------- |
| CodeQL                | SAST for Python, JS/TS, and Actions workflows    | push, PR, weekly  |
| OSV-Scanner           | Known CVEs across all dependency manifests (SCA) | push, PR, weekly  |
| OpenSSF Scorecard     | Repository security posture                      | push, PR, weekly  |
| Gitleaks              | Secret scanning on release                       | release           |
| ruff (pre-commit)     | Python static analysis                           | every push and PR |
| Renovate / Dependabot | Dependency freshness and vulnerability alerts    | weekly            |

See [CI/CD Workflows](ci-cd.md) for how each scan is wired into the pipeline.

## Repository hardening

- Workflows declare `permissions: {}` at the top level and grant the minimal
  scopes per job; the default `GITHUB_TOKEN` is read-only.
- Branch protection is enforced through an aggregating `ci-success` gate on each
  workflow (see [CI/CD Workflows](ci-cd.md)).
- [Allstar](https://github.com/strangeflavoured/health/tree/main/.allstar)
  policies guard branch protection, binary artifacts, dangerous workflow
  patterns, action pinning, and outside collaborator access.
- Forked pull requests cannot read CI secrets; the integration test is gated on
  the head repository matching the base repository.
