# Contributing

This project is a personal health data platform. Contributions are welcome for
bug fixes and improvements, but the scope is intentionally narrow — please open
an issue before starting significant new work so we can discuss fit.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Permissions Policy](#permissions-policy)
- [Testing Policy](#testing-policy)
- [Reporting Issues](#reporting-issues)
- [Security Vulnerabilities](#security-vulnerabilities)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Dependency Management](#dependency-management)
- [Commit Style](#commit-style)
- [Pull Request Process](#pull-request-process)
- [CI Checks](#ci-checks)

---

(code-of-conduct)=

## Code of Conduct

Be respectful. Contributions that are hostile, dismissive, or otherwise
unpleasant will not be accepted.

---

(permissions-policy)=

## Permissions policy

New contributors are granted read access by default.
Write or admin access is only granted after at least one merged PR
and review by an existing maintainer.

---

(testing-policy)=

## Testing policy

All significant changes MUST include new or updated tests.
PRs without test coverage for changed functionality will not be merged.

---

(reporting-issues)=

## Reporting Issues

Search existing issues before opening a new one. When filing a bug, include:

- A minimal reproducible example
- The relevant part of the stack trace or error output
- Your OS and Python/Node versions if relevant
- Whether the failure is consistent or intermittent

---

(security-vulnerabilities)=

## Security Vulnerabilities

Do not open a public issue for security vulnerabilities. Use GitHub's private
advisory reporting instead:

👉 [Report a vulnerability](https://github.com/strangeflavoured/health/security/advisories/new)

See [SECURITY.md](https://github.com/strangeflavoured/health/blob/main/SECURITY.md) for the full policy.

---

(development-setup)=

## Development Setup

### Prerequisites

- Docker and Docker Compose v2.40+
- Python 3.12
- Node.js 25 (LTS)
- `pass` (GPG-backed secret store) — required for the Redis mTLS stack

### Clone and install tooling

```bash
git clone https://github.com/strangeflavoured/health.git
cd health

# Install Python tooling (hashed requirements)
pip install --require-hashes -r pip-requirements.txt
pip install --require-hashes -r requirements-dev.txt

# Install the full dev virtualenv
python -m venv .venv
.venv/bin/pip install --require-hashes \
  -r src/requirements.txt \
  -r requirements-dev.txt \
  -r backend/requirements/base.txt \
  -r backend/requirements/tests.txt \
  -r docs/requirements.txt

# Install frontend dependencies
cd frontend && npm ci && cd ..

# Install pre-commit hooks
pre-commit install
```

### Starting the stack

Certificates and Redis ACL credentials are managed via `pass`. Run the helper
script to materialise secrets onto a tmpfs before starting:

```bash
./scripts/compose-wrapper.sh up
```

Stop and clean up:

```bash
./scripts/compose-wrapper.sh down
```

---

(making-changes)=

## Making Changes

- Work on a branch off `main`. Branch names should be descriptive:
  `fix/redis-acl-parsing`, `feat/add-sleep-metric`, `chore/bump-django`.
- Keep commits focused. One logical change per commit.
- Update or add tests for any behaviour you change.
- If you add a new Python dependency, see [Dependency Management](#dependency-management).
- If you modify Docker images or compose files, run the full stack integration
  test locally before pushing.

---

(testing)=

## Testing

All tests run inside Docker. The CI suite validates this path; running tests
locally via Docker is the authoritative way to check your changes.

### Backend tests (pytest, Django)

```bash
docker compose -f docker/compose.yml run backend-test
```

Coverage is enforced at **80%**. Tests that drop below this threshold will fail CI.

### Source / ETL tests

```bash
docker compose -f docker/compose.yml run test-runner
```

### Frontend tests (Vitest)

```bash
docker compose -f docker/compose.yml run frontend-test
```

Coverage reports are written to `test-output/coverage-js/lcov.info`.

### Script tests

Python scripts are tested with pytest; bash scripts are tested with
[bats](https://github.com/bats-core/bats-core):

```bash
docker compose -f docker/compose.yml run scripts-tests   # Python
docker compose -f docker/compose.yml run bats-tests       # Bash
```

### Running pre-commit locally

pre-commit runs on every push and PR in CI, but you can run it manually:

```bash
# Against changed files only
pre-commit run

# Against all files
pre-commit run --all-files
```

The `compile-requirements` hook is skipped in CI on PR runs; you do not need
to run it manually in most cases.

---

(dependency-management)=

## Dependency Management

Dependencies are managed with `pip-compile` (hashed output) and Renovate.

### Python

Requirements are defined in `.in` files and compiled to `.txt` files with
`--generate-hashes`. **Do not edit `.txt` files directly.**

To add or update a Python dependency:

1. Add or modify the entry in the appropriate `.in` file.
2. Run the requirements maintenance workflow locally or trigger it in CI:

```bash
python -m ci.requirements_maintenance.recompile
```

3. Verify the recompiled `.txt` file contains `--hash=` entries:

```bash
grep -q -- '--hash=' path/to/requirements.txt && echo ok
```

All CI installs use `pip install --require-hashes`. PRs that introduce
requirement files without hashes will fail the verification step.

### JavaScript

Frontend dependencies are managed via `npm`. Edit `frontend/package.json` and
run `npm install` to update `package-lock.json`. Renovate handles automated
version bumps.

### GitHub Actions and Docker images

Renovate manages SHA-pinned Actions and Docker base image updates. All Action
`uses:` references must be pinned to a full commit SHA with a version comment,
for example:

```yaml
uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
```

Do not use mutable tags (`@v4`, `@main`) in workflow files.

---

(commit-style)=

## Commit Style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>
```

Common types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`.

Examples:

```
feat(src): add resting heart rate metric
fix(backend): handle empty Apple Health export gracefully
chore(deps): recompile requirements
ci(scorecard): add Token-Permissions check
```

The summary should be lowercase, imperative mood, no trailing period, under
72 characters.

---

(pull-request-process)=

## Pull Request Process

1. Ensure all CI checks pass before requesting review.
2. Fill in the PR description — what changed, why, and any testing notes.
3. Keep PRs small and focused. Large PRs are harder to review and more likely
   to introduce subtle bugs.
4. If a PR introduces a new workflow or modifies an existing one, confirm that
   all Actions are SHA-pinned and per-job `permissions` blocks are minimal.
5. The `deps-bot` GitHub App may push a commit to your branch to recompile
   requirements if your changes touched `.in` files. This is expected.
6. PRs from forks require maintainer approval before CI secrets are available
   to the integration test workflow.

---

(ci-checks)=

## CI Checks

All checks must be green before merging. Here is what each workflow validates:

| Workflow                   | Trigger                  | What it checks                                                      |
| -------------------------- | ------------------------ | ------------------------------------------------------------------- |
| `pre-commit`               | PR, push to main         | ruff lint/format, type stubs, trailing whitespace, YAML/JSON syntax |
| `tests`                    | PR, push to main         | Backend, frontend, and ETL unit tests with coverage                 |
| `docker-stack`             | PR, push to main         | Full Docker Compose integration (Redis mTLS, backend, frontend)     |
| `scripts`                  | PR, push to main         | Python and bash script tests                                        |
| `sphinx`                   | PR, push to main         | Documentation builds without errors                                 |
| `requirements-maintenance` | PR, push to main, weekly | Dependency freshness, hash integrity, conflict detection            |
| `codeql`                   | PR, push to main, weekly | SAST for Python, JS/TS, Actions                                     |
| `osv-scan`                 | PR, push to main, weekly | Known CVEs in dependencies                                          |
| `scorecard`                | PR, push to main, weekly | OpenSSF security posture                                            |

A `ci-success` gate job aggregates per-workflow results. Branch protection
requires this job to pass before merge.
