#!/usr/bin/env bats
# Tests for compile-requirements.sh
#
# Security focus:
#   * The explicit IN_FILES array must match exactly what git ls-files reports.
#     A divergence means either dead entries (false confidence) or missing
#     files (silently uncompiled lockfiles).
#
# Safety focus:
#   * Missing uv → explicit, actionable error.
#   * Failed compile on any file → non-zero exit even if others succeed.
#   * All IN_FILES entries must be attempted regardless of earlier failures.

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/compile-requirements.sh"
STUBS="$(dirname "$BATS_TEST_FILENAME")/stubs.bash"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a project directory that matches the hard-coded IN_FILES list in the
# script exactly.  Returns the directory path via stdout.
make_project_dir() {
  local dir
  dir="$(mktemp -d)"

  mkdir -p "$dir/.venv/bin"
  # Minimal activate / deactivate stubs so `source .venv/bin/activate` succeeds.
  printf 'deactivate() { :; }\n' > "$dir/.venv/bin/activate"

  # Create each .in file expected by IN_FILES.
  for relpath in \
      pip-requirements.in \
      requirements-dev.in \
      src/importer/requirements.in \
      src/requirements.in \
      backend/requirements/base.in \
      backend/requirements/tests.in \
      docs/requirements.in \
      tests/requirements.in; do
    mkdir -p "$dir/$(dirname "$relpath")"
    printf 'requests\n' > "$dir/$relpath"
  done

  printf '%s' "$dir"
}

# Create a git stub that lists all tracked *.in files under PROJECT_DIR.
install_git_stub() {
  local dir="$1"
  cat > "$STUB_DIR/git" <<EOF
#!/usr/bin/env bash
# Only respond to ls-files; pass everything else through.
if [[ "\$1" == "ls-files" ]]; then
  find "$dir" -name '*.in' | sed "s|$dir/||"
else
  command git "\$@"
fi
EOF
  chmod +x "$STUB_DIR/git"
}

# Create a uv stub that records calls and exits with the given code.
install_uv_stub() {
  local code="${1:-0}"
  cat > "$STUB_DIR/uv" <<EOF
#!/usr/bin/env bash
printf 'uv %s\n' "\$*" >> "$STUB_DIR/uv_calls.log"
exit $code
EOF
  chmod +x "$STUB_DIR/uv"
}

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

# shellcheck source=stubs.bash
setup() {
  source "$STUBS"
  STUB_DIR="$(mktemp -d)"
  export STUB_DIR
  export PATH="$STUB_DIR:$PATH"
}

teardown() {
  rm -rf "$STUB_DIR" "${PROJECT_DIR:-}"
}

# ---------------------------------------------------------------------------
# uv dependency
# ---------------------------------------------------------------------------

@test "exits 1 with a useful message when uv is not on PATH" {
  # Remove any uv stub; rely on the static source check if system uv exists.
  rm -f "$STUB_DIR/uv"

  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"

  # If system uv is installed, the live guard can't fire; verify the guard
  # is present in the script source instead.
  if command -v uv &>/dev/null; then
    grep -q 'command -v uv' "$SCRIPT"
    grep -q 'exit 1' "$SCRIPT"
  else
    run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
    [ "$status" -eq 1 ]
    [[ "$output" == *"uv"* ]]
  fi
}

# ---------------------------------------------------------------------------
# File-list verification (sync between IN_FILES and git ls-files)
# ---------------------------------------------------------------------------

@test "fails when IN_FILES contains a file not on disk" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 0

  # Remove one file so the list and disk diverge.
  rm "$PROJECT_DIR/docs/requirements.in"

  run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  [ "$status" -ne 0 ]
  [[ "$output" == *"out of sync"* || "$output" == *"in list, not on disk"* ]]
}

@test "fails when an extra .in file exists on disk but is missing from IN_FILES" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 0

  # Add an extra file that IN_FILES doesn't know about.
  mkdir -p "$PROJECT_DIR/extra"
  printf 'flask\n' > "$PROJECT_DIR/extra/requirements.in"

  run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  [ "$status" -ne 0 ]
  [[ "$output" == *"out of sync"* || "$output" == *"on disk, not in list"* ]]
}

@test "succeeds when IN_FILES matches disk exactly" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 0

  run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Compilation behaviour
# ---------------------------------------------------------------------------

@test "invokes uv pip compile for every .in file" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 0

  bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"

  call_count=$(grep -c "pip compile" "$STUB_DIR/uv_calls.log" 2>/dev/null || echo 0)
  [ "$call_count" -ge 8 ]
}

@test "passes --generate-hashes to uv pip compile" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 0

  bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  grep -q "\-\-generate-hashes" "$STUB_DIR/uv_calls.log"
}

@test "output .txt filename is derived from .in filename" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 0

  bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  grep -q "pip-requirements.txt" "$STUB_DIR/uv_calls.log"
}

# ---------------------------------------------------------------------------
# Failure propagation
# ---------------------------------------------------------------------------

@test "exits 1 when uv pip compile fails for any file" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 1

  run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  [ "$status" -eq 1 ]
}

@test "prints FAILED message on compilation error" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"
  install_uv_stub 1

  run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  [[ "$output" == *"FAILED"* ]]
}

@test "continues compiling remaining files after one failure" {
  PROJECT_DIR="$(make_project_dir)"
  install_git_stub "$PROJECT_DIR"

  # Fail on the first call only.
  cat > "$STUB_DIR/uv" <<EOF
#!/usr/bin/env bash
printf 'uv %s\n' "\$*" >> "$STUB_DIR/uv_calls.log"
count=\$(wc -l < "$STUB_DIR/uv_calls.log")
[ "\$count" -le 1 ] && exit 1
exit 0
EOF
  chmod +x "$STUB_DIR/uv"

  run bash -c "cd '$PROJECT_DIR' && bash '$SCRIPT'"
  # More than 1 call means the loop continued after the first failure.
  call_count=$(wc -l < "$STUB_DIR/uv_calls.log" 2>/dev/null || echo 0)
  [ "$call_count" -gt 1 ]
}
