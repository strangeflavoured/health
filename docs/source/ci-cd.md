# CI/CD Workflows

All automation lives in `.github/workflows/`. Every workflow declares
`permissions: {}` at the top level and grants the minimum scopes per job, and
every third-party action is pinned to a full commit SHA. Most workflows follow
the same shape:

1. a **`changes`** job uses `dorny/paths-filter` to decide which parts of the
   repo were touched, so expensive jobs are skipped when irrelevant;
2. one or more **work** jobs run only when their filter matched;
3. a final **`ci-success`** job runs `if: always()` and fails if any upstream
   job failed. Branch protection requires this aggregating gate, which keeps the
   required-check list stable even as inner jobs are skipped.

## Continuous checks (push / PR)

### `pre-commit`

Runs the full pre-commit suite (ruff lint/format, whitespace, YAML/JSON syntax,
type stubs). It restores a cached `.venv` and pre-commit environments, installs
hashed requirements, and runs only against the PR diff
(`--from-ref`/`--to-ref`) to stay fast. A `workflow_dispatch` input allows a
manual `--all-files` run.

### `tests`

Builds the test images with `docker buildx bake` and runs three suites as
Compose services, each writing JUnit XML and coverage into a shared
`test-output/` mount:

- `test-runner` — `src/` ETL unit tests;
- `backend-test` — Django/pytest, gated at `--cov-fail-under=80`;
- `frontend-test` — Vitest with lcov coverage.

Results are published to the PR via `dorny/test-reporter` and uploaded to
Codecov. The suites are selected by the `changes` filter, so a frontend-only PR
does not rebuild the backend.

### `docker-stack`

The integration test. It bakes the `infra`/`dev` (and optionally `sandbox`)
images, materialises Redis mTLS secrets from GitHub Actions secrets via
`scripts/load-ci-secrets.sh`, writes a CI Compose override, starts
`redis`/`redisinsight`/`backend`/`frontend`, and polls Docker health status
until everything reports healthy. Logs are dumped on failure and the stack
(plus the secret tmpfs) is always torn down. Forked PRs are skipped because they
cannot access the mTLS secrets.

### `scripts`

Runs the script test suites: pytest for the Python requirements-maintenance
tooling and [bats](https://github.com/bats-core/bats-core) for the shell
scripts.

### `sphinx`

Builds the documentation inside the `docs` image (`make -C docs clean html`).
On release it additionally snapshots the README badges, rewrites their URLs to
the versioned Pages path, and uploads the rendered site as an artifact for the
release workflow to publish.

## Security scanning

### `codeql`

CodeQL SAST for `actions`, `javascript-typescript`, and `python` using the
`security-and-quality` query pack. Runs on push, PR, and a weekly schedule;
results upload to code scanning as SARIF.

### `osv-scan`

`google/osv-scanner-action` recursively scans every dependency manifest against
the OSV database on push, PR, and weekly.

### `scorecard`

OpenSSF Scorecard evaluates repository security posture and publishes results to
the OSSF API and code scanning on push, PR, and weekly.

## Dependency maintenance

### `requirements-maintenance`

Triggered by changes to any requirements file, weekly on Mondays, or manually.
The `analyse` job builds a dependency DAG over all `*.in` files
(`build_dag`), asserts the DAG covers every file on disk, detects unused
packages (`deptry`), checks for newer versions (`check_updates`), recompiles to
verify there are no `pip-compile` errors, and checks per-stack install
conflicts (`check_conflicts`). Findings are summarised and uploaded as an
artifact.

When updates or conflicts are found, `apply-fixes` runs `recompile`, verifies
every regenerated file still carries `--hash=` entries, and either commits to
the PR branch or opens a `chore(deps): recompile requirements` PR via a scoped
GitHub App token. Renovate and Dependabot complement this for npm, Actions, and
Docker ecosystems.

## Release

### `release`

Triggered by publishing a GitHub Release. It runs a pre-release Gitleaks +
OSV scan, builds the docs (reusing `sphinx.yml`), generates a CycloneDX SBOM,
and renders an OpenVEX document. It then deploys the versioned docs to GitHub
Pages, attaches the SBOM and VEX to the release, signs the docs/SBOM/VEX with
`actions/attest-build-provenance`, and finally commits the release notes back
into `CHANGELOG.md` using a dedicated GitHub App token (so the bot commit is
attributable and the default token stays read-only).
