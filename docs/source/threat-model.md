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
