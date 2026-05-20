#!/usr/bin/env bats
# Tests for compose-wrapper.sh
#
# Security focus:
#   * Secrets directory lands at 700, files at 400.
#   * ACL passwords are stored as hashes in users.acl.
#   * write_secrets fails fast if pass returns empty for any key.
#   * 'down' always removes the secrets directory regardless of container state.
#
# Safety focus:
#   * No-argument invocation exits non-zero with a helpful message.
#   * Foreground 'up' cleans up secrets via EXIT trap.
#   * Detached 'up -d' preserves secrets and warns the operator.
#   * Pass-through commands (logs, ps, exec, …) are forwarded untouched.

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/compose-wrapper.sh"
STUBS="$(dirname "$BATS_TEST_FILENAME")/stubs.bash"

# The script derives SECRETS_DIR from id -u; compute the same value here.
SCRIPT_SECRETS_DIR="/dev/shm/health-secrets-$(id -u)"

# shellcheck source=stubs.bash
setup() {
  source "$STUBS"
  STUB_DIR="$(mktemp -d)"
  export STUB_DIR
  export PATH="$STUB_DIR:$PATH"

  DOCKER_CALL_LOG="$(mktemp)"
  export DOCKER_CALL_LOG

  create_pass_stub
  create_docker_stub

  # Remove any leftover secrets directory from a previous run.
  rm -rf "$SCRIPT_SECRETS_DIR"
}

teardown() {
  rm -rf "$STUB_DIR" "$DOCKER_CALL_LOG"
  rm -rf "$SCRIPT_SECRETS_DIR"
}

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

@test "exits 1 and prints an error when called with no arguments" {
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"arg"* || "$output" == *"arg"* ]]
}

# ---------------------------------------------------------------------------
# 'up' — foreground mode
# ---------------------------------------------------------------------------

@test "'up' calls docker compose up" {
  run bash "$SCRIPT" up
  grep -q "compose" "$DOCKER_CALL_LOG"
  grep -q "up" "$DOCKER_CALL_LOG"
}

@test "'up' removes secrets directory after foreground exit" {
  bash "$SCRIPT" up
  [ ! -d "$SCRIPT_SECRETS_DIR" ]
}

@test "'up' passes extra flags through to docker compose" {
  run bash "$SCRIPT" up --build
  grep -q "\-\-build" "$DOCKER_CALL_LOG"
}

# ---------------------------------------------------------------------------
# 'up -d' — detached mode
# ---------------------------------------------------------------------------

@test "'up -d' leaves secrets directory in place" {
  run bash "$SCRIPT" up -d
  [ "$status" -eq 0 ]
  [ -d "$SCRIPT_SECRETS_DIR" ]
}

@test "'up --detach' leaves secrets directory in place" {
  run bash "$SCRIPT" up --detach
  [ "$status" -eq 0 ]
  [ -d "$SCRIPT_SECRETS_DIR" ]
}

@test "'up -d' prints a warning that secrets must be cleaned up manually" {
  run bash "$SCRIPT" up -d
  [[ "$output" == *"down"* || "$output" == *"secret"* || "$output" == *"clean"* ]]
}

@test "'up -d' output includes the path to the secrets directory" {
  run bash "$SCRIPT" up -d
  [[ "$output" == *"$SCRIPT_SECRETS_DIR"* ]]
}

# ---------------------------------------------------------------------------
# 'down'
# ---------------------------------------------------------------------------

@test "'down' calls docker compose down" {
  mkdir -p "$SCRIPT_SECRETS_DIR"
  run bash "$SCRIPT" down
  grep -q "compose" "$DOCKER_CALL_LOG"
  grep -q "down" "$DOCKER_CALL_LOG"
}

@test "'down' removes the secrets directory" {
  mkdir -p "$SCRIPT_SECRETS_DIR"
  touch "$SCRIPT_SECRETS_DIR/ca.pem"
  bash "$SCRIPT" down
  [ ! -d "$SCRIPT_SECRETS_DIR" ]
}

@test "'down' prints a cleanup confirmation" {
  mkdir -p "$SCRIPT_SECRETS_DIR"
  run bash "$SCRIPT" down
  [[ "$output" == *"clean"* || "$output" == *"Secrets"* || "$output" == *"removed"* ]]
}

@test "'down' passes extra flags to docker compose" {
  mkdir -p "$SCRIPT_SECRETS_DIR"
  run bash "$SCRIPT" down --volumes
  grep -q "\-\-volumes" "$DOCKER_CALL_LOG"
}

# ---------------------------------------------------------------------------
# 'build'
# ---------------------------------------------------------------------------

@test "'build' calls docker buildx bake" {
  run bash "$SCRIPT" build
  grep -q "buildx" "$DOCKER_CALL_LOG"
  grep -q "bake" "$DOCKER_CALL_LOG"
}

@test "'build' passes extra args to buildx bake" {
  run bash "$SCRIPT" build --no-cache
  grep -q "\-\-no-cache" "$DOCKER_CALL_LOG"
}

# ---------------------------------------------------------------------------
# Pass-through commands
# ---------------------------------------------------------------------------

@test "'logs' is passed through to docker compose" {
  run bash "$SCRIPT" logs
  grep -q "logs" "$DOCKER_CALL_LOG"
}

@test "'ps' is passed through to docker compose" {
  run bash "$SCRIPT" ps
  grep -q "ps" "$DOCKER_CALL_LOG"
}

@test "'exec' with arguments is passed through" {
  run bash "$SCRIPT" exec redis redis-cli ping
  grep -q "exec" "$DOCKER_CALL_LOG"
}

# ---------------------------------------------------------------------------
# Secrets content and permissions (detached mode, secrets persist)
# ---------------------------------------------------------------------------

@test "secrets directory is created with 700 permissions" {
  bash "$SCRIPT" up -d
  perms=$(stat -c '%a' "$SCRIPT_SECRETS_DIR")
  [ "$perms" = "700" ]
}

@test "certificate files are non-empty after 'up -d'" {
  bash "$SCRIPT" up -d
  [ -s "$SCRIPT_SECRETS_DIR/ca.pem" ]
  [ -s "$SCRIPT_SECRETS_DIR/server.pem" ]
}

@test "password files are non-empty after 'up -d'" {
  bash "$SCRIPT" up -d
  [ -s "$SCRIPT_SECRETS_DIR/admin_password" ]
  [ -s "$SCRIPT_SECRETS_DIR/app_password" ]
}

@test "ACL file disables default user after 'up -d'" {
  bash "$SCRIPT" up -d
  grep -q "user default off" "$SCRIPT_SECRETS_DIR/users.acl"
}

@test "secret files have 400 permissions after 'up -d'" {
  bash "$SCRIPT" up -d
  local bad=0
  while IFS= read -r -d '' f; do
    perms=$(stat -c '%a' "$f")
    if [ "$perms" != "400" ]; then
      echo "wrong perms $perms on $f" >&2
      bad=1
    fi
  done < <(find "$SCRIPT_SECRETS_DIR" -type f -print0)
  [ "$bad" -eq 0 ]
}

@test "ACL password stored as SHA-256 hash not plaintext" {
  bash "$SCRIPT" up -d
  # Must match #<64-hex-chars>
  grep -qE "user admin on #[0-9a-f]{64}" "$SCRIPT_SECRETS_DIR/users.acl"
}

# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@test "fails non-zero when pass returns empty for a secret" {
  # Override pass to return empty for ca.pem
  cat > "$STUB_DIR/pass" <<'STUB'
#!/usr/bin/env bash
key="${*: -1}"
[[ "$key" == "health/redis/certs/ca.pem" ]] && printf '' || printf 'FAKE-VALUE'
STUB
  chmod +x "$STUB_DIR/pass"
  run bash "$SCRIPT" up -d
  [ "$status" -ne 0 ]
}

@test "full up-d/down lifecycle removes all secrets" {
  bash "$SCRIPT" up -d
  [ -d "$SCRIPT_SECRETS_DIR" ]
  bash "$SCRIPT" down
  [ ! -d "$SCRIPT_SECRETS_DIR" ]
}
