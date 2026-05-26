# Roadmap

This roadmap describes the intended direction of HealthAnalyser. It is a
personal project with an intentionally narrow scope; items here are priorities
rather than commitments, and timelines are best-effort.

## Status

The project is in active development on the `main` branch. The current focus is
hardening the existing ingest → store → serve pipeline and the security and
supply-chain posture around it, rather than broad feature expansion.

## Near term

- **Finish CI/CD hardening.** Resolve the remaining Vite/Docker permission issue
  in the `docker-stack` integration workflow and continue tightening per-job
  permissions, action pinning, and container hardening.
- **Signed release tags.** Move to SSH-signed, annotated tags for every release
  (see [Cutting a release](https://github.com/strangeflavoured/health/blob/main/docs/source/cutting-a-release.md)).
- **Dependency hygiene.** Keep the hashed-requirements pipeline, Renovate, and
  Dependabot current across all ecosystems; keep the OpenVEX triage document up
  to date as advisories are assessed.

## Medium term

- **Coverage and test breadth.** Bring the ETL and frontend suites in line with
  the backend's 80% statement-coverage gate and add regression tests for fixed
  defects.
- **Accessibility pass.** Audit the React frontend against WCAG basics
  (semantic markup, contrast, keyboard navigation) and document the results.
- **API surface.** Expand and document the read API for stored health metrics.

## Longer term / under consideration

- **End-user authentication.** Multi-user authentication is currently out of
  scope (see the [Threat Model](https://github.com/strangeflavoured/health/blob/main/docs/source/threat-model.md)); adding it would
  be a prerequisite for any deployment beyond a single trusted host or private
  network.
- **Additional Apple Health metrics and richer visualisations.**

## Out of scope

- Multi-tenant or public, internet-exposed deployment.
- Hosting or processing anyone else's health data as a service.

Suggestions are welcome via [GitHub issues](https://github.com/strangeflavoured/health/issues);
please open an issue to discuss before starting significant new work.
