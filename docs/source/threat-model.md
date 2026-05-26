# Threat Model

Version: 1.1 | Last reviewed: 2026-05-24

## Scope

HealthAnalyser is a single-node, self-hosted platform that ingests Apple Health
exports into Redis TimeSeries and exposes them through a Django API and React
frontend. This model covers the ETL importer (`src/`), the Django backend
(`backend/`), the React frontend (`frontend/`), the Redis storage layer and its
mTLS configuration (`docker/`), and the CI/CD automation (`.github/`,
`scripts/`).

It does **not** cover a multi-tenant or internet-exposed deployment. The stack
is intended to run on a trusted host (or over a private Tailscale network) for a
single user; multi-user authentication is not yet implemented and is therefore
out of scope rather than assumed-secure.

## Assets

| Asset                                  | Sensitivity | Notes                                                                                 |
| -------------------------------------- | ----------- | ------------------------------------------------------------------------------------- |
| Apple Health records (PHI)             | Critical    | Body, vitals, reproductive, and symptom data; must never leave the host in plaintext. |
| Redis ACL passwords                    | High        | Grant write/read access to the health keyspace.                                       |
| TLS private keys (CA, server, clients) | High        | Compromise breaks mutual authentication.                                              |
| GPG key protecting the `pass` store    | Critical    | Root of trust for all local secrets.                                                  |
| CI secrets (certs, password hashes)    | High        | Stored as GitHub Actions secrets; used only by the integration test.                  |
| Release signing / app tokens           | High        | GitHub App private keys used by the release and deps workflows.                       |

## Trust boundaries

- **Browser ↔ frontend (Vite/React)** — local or Tailscale-only; no public exposure.
- **Frontend ↔ backend API** — same host network; input validated server-side.
- **Backend / importer ↔ Redis** — mutual TLS, per-user ACLs, `HK*` keyspace scoping.
- **`pass`/GPG ↔ tmpfs ↔ containers** — secrets decrypted to a `0700` tmpfs and mounted read-only at `/run/secrets`.
- **CI/CD ↔ repository** — least-privilege `GITHUB_TOKEN`; forked PRs cannot read secrets.

## Attack surface

| Entry point                      | Threat                                                 | Mitigation                                                                               |
| -------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Apple Health `export.zip` import | Malicious/malformed XML (XXE, zip bombs, schema abuse) | Parsed with `defusedxml`; size and structure validated in `data_check` before any write. |
| API endpoints                    | Unauthorized or malformed access                       | Server-side validation; read paths scoped to the `insight`/`app` ACL users.              |
| Redis                            | Credential theft, unscoped commands                    | mTLS, disabled `default` user, least-privilege ACL command sets, hashed passwords.       |
| Local secrets                    | Disk persistence / env leakage                         | tmpfs-only materialisation, `0400` files, no secrets in container env.                   |
| Dependencies                     | Supply-chain compromise                                | Hashed requirements, SHA-pinned actions and images, CodeQL/OSV/Scorecard, SBOM + VEX.    |
| CI/CD                            | Secret exfiltration via PRs                            | Scoped tokens, forked-PR secret gating, Allstar dangerous-workflow checks.               |

## Critical code paths

1. **Import → validation → upload** — `parser` → `transform` → `data_check` → `pipeline` (Redis TimeSeries write).
2. **Failure handling** — per-row failures persisted to JSON so retries survive across runs.
3. **Health read path** — API auth/ACL check → Redis query → response serialisation.
4. **Secret materialisation** — `pass` decrypt → tmpfs → container mount → ACL generation.

## Out of scope

- Physical access to the host machine.
- Third-party infrastructure (GitHub, Tailscale, Apple).
- A hardened multi-user / public deployment (not a current goal).

## Known risks and accepted mitigations

| Risk                                  | Likelihood | Impact   | Mitigation                                                                       | Status    |
| ------------------------------------- | ---------- | -------- | -------------------------------------------------------------------------------- | --------- |
| Dependency CVEs                       | Medium     | Medium   | Automated scanning (OSV/CodeQL/Scorecard) + OpenVEX triage                       | Active    |
| No end-user authentication yet        | Medium     | High     | Restrict exposure to localhost/Tailscale; documented as out-of-scope until added | Accepted  |
| Loss of the GPG key                   | Low        | Critical | Offline encrypted backup of the private key (see pass-secrets)                   | Mitigated |
| Host compromise exposes tmpfs secrets | Low        | High     | Single-user trusted host; tmpfs wiped on `down`/reboot                           | Accepted  |

## Assurance Case

This section presents the project's assurance case: an explicit, top-level
argument for why HealthAnalyser is adequately secure for its intended use,
together with the evidence that supports it. It complements the threat analysis
above by stating the overarching claim and showing how the individual
mitigations combine to support it.

### Top-level claim

> Under the stated trust assumptions — a single user operating on a trusted host
> or private network — HealthAnalyser adequately protects locally stored
> personal health information (PHI) against unauthorised disclosure, tampering,
> and supply-chain compromise.

The claim is deliberately scoped. It does **not** assert security for a
multi-tenant or internet-exposed deployment; that configuration is out of scope
(see [Scope](#scope) and [Out of scope](#out-of-scope)) and would require
end-user authentication that the project does not yet implement.

### Supporting arguments and evidence

The top-level claim is decomposed into sub-claims, each backed by a specific
control and its evidence.

| Sub-claim                                   | Argument                                                                                                                                                                   | Evidence                                                                                               |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| PHI is not disclosed in transit             | All access to the storage layer is over mutual TLS; the non-TLS port is disabled and the `default` Redis user is disabled.                                                 | [Security: Transport security and access control](security.md); Redis mTLS configuration in `docker/`. |
| PHI access is least-privilege               | Redis ACL users are scoped to minimal command sets over the `HK*` keyspace; credentials are hashed, never stored in plaintext.                                             | [Security: Transport security and access control](security.md); ACL generation in the compose wrapper. |
| Secrets do not persist or leak              | Local secrets live only in a GPG-backed `pass` store and are materialised to a `0700` tmpfs mounted read-only into containers; never passed via environment variables.     | [Security: Secrets handling](security.md); [Secrets Management with `pass`](pass-secrets.md).          |
| Malicious input cannot subvert ingest       | Apple Health exports are parsed with `defusedxml` (XXE-resistant) and validated for size and structure before any write.                                                   | [Attack surface](#attack-surface) table; `data_check` and `parser` in `src/`.                          |
| Dependencies are not a silent attack vector | Requirements are hash-pinned and installed with `--require-hashes`; Actions and base images are pinned by SHA/digest; CodeQL, OSV-Scanner, and Scorecard run continuously. | [Security: Supply-chain assurance](security.md); [CI/CD Workflows](ci-cd.md).                          |
| Releases are attributable and verifiable    | Release tags are signed (annotated) and release artifacts carry Sigstore build-provenance attestations.                                                                    | [Cutting a release](cutting-a-release.md); `release.yml`.                                              |
| The development pipeline cannot be hijacked | `GITHUB_TOKEN` is read-only with minimal per-job escalation; forked PRs cannot read secrets; Allstar guards dangerous workflow patterns.                                   | [Security: Repository hardening](security.md); [CI/CD Workflows](ci-cd.md).                            |

### Accepted residual risks

The assurance case is bounded by the risks accepted in
[Known risks and accepted mitigations](#known-risks-and-accepted-mitigations).
The most significant are the absence of end-user authentication (mitigated by
restricting exposure to localhost/Tailscale and documenting it as out of scope)
and the single-maintainer bus factor (mitigated by an offline-encrypted backup
of the GPG key). These are conscious trade-offs appropriate to a single-user
personal project, not unaddressed gaps.

### Confidence and limitations

This is a self-assessed assurance case maintained by the sole maintainer; it has
not been independently audited. Its validity is contingent on the trust
assumptions holding — in particular, that the host machine and the maintainer's
GPG key remain uncompromised. Should the project's scope expand toward
multi-user or public deployment, this assurance case must be revisited before
the top-level claim can be relied upon.
