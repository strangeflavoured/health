#!/usr/bin/env bats
# Tests for load-ci-secrets.sh
#
# Security focus:
#   * All 14 required env-var families must be validated.
#   * Empty or near-empty (whitespace-only) decoded values are rejected.
#   * ACL file must contain correct user names, Redis key patterns, and
#     command sets — a misconfigured ACL is a privilege-escalation path.
#   * Files land at 444 (world-readable-only), directory at 700.
#
# Safety focus:
#   * Missing env vars produce an explicit, named error message.
#   * Leftover state from a prior run is cleaned before writing.

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/load-ci-secrets.sh"
STUBS="$(dirname "$BATS_TEST_FILENAME")/stubs.bash"

# shellcheck source=stubs.bash
setup() {
  source "$STUBS"
  export SECRETS_DIR
  SECRETS_DIR="$(mktemp -d)"
  export_fake_ci_secrets
}

teardown() {
  rm -rf "$SECRETS_DIR"
}

# ---------------------------------------------------------------------------
# Happy-path: all secrets materialise
# ---------------------------------------------------------------------------

@test "exits 0 when all required variables are set" {
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
}

@test "creates ca.pem, server.pem, and all cert files" {
  bash "$SCRIPT"
  [ -f "$SECRETS_DIR/ca.pem" ]
  [ -f "$SECRETS_DIR/server.pem" ]
  [ -f "$SECRETS_DIR/healthcheck.pem" ]
  [ -f "$SECRETS_DIR/redisinsight.pem" ]
  [ -f "$SECRETS_DIR/app.pem" ]
}

@test "creates all key files" {
  bash "$SCRIPT"
  [ -f "$SECRETS_DIR/server.key" ]
  [ -f "$SECRETS_DIR/healthcheck.key" ]
  [ -f "$SECRETS_DIR/redisinsight.key" ]
  [ -f "$SECRETS_DIR/app.key" ]
}

@test "creates all password files" {
  bash "$SCRIPT"
  [ -f "$SECRETS_DIR/admin_password" ]
  [ -f "$SECRETS_DIR/app_password" ]
  [ -f "$SECRETS_DIR/healthcheck_password" ]
  [ -f "$SECRETS_DIR/insight_password" ]
}

@test "creates users.acl" {
  bash "$SCRIPT"
  [ -f "$SECRETS_DIR/users.acl" ]
}

@test "base64 decoding is correct" {
  bash "$SCRIPT"
  content=$(cat "$SECRETS_DIR/ca.pem")
  [ "$content" = "fake-ca-cert" ]
}

@test "password files contain the expected plaintext password" {
  bash "$SCRIPT"
  content=$(cat "$SECRETS_DIR/admin_password")
  [ "$content" = "adminpassword" ]
}

# ---------------------------------------------------------------------------
# ACL content — security-critical
# ---------------------------------------------------------------------------

@test "ACL disables the default user" {
  bash "$SCRIPT"
  grep -q "user default off" "$SECRETS_DIR/users.acl"
}

@test "ACL admin user has full permissions" {
  bash "$SCRIPT"
  grep -q "user admin on" "$SECRETS_DIR/users.acl"
  grep -q "+@all" "$SECRETS_DIR/users.acl"
}

@test "ACL app user is restricted to the HK key namespace" {
  bash "$SCRIPT"
  app_line=$(grep "user app on" "$SECRETS_DIR/users.acl")
  [[ "$app_line" == *"~HK*"* ]]
}

@test "ACL app user does NOT have +@all" {
  bash "$SCRIPT"
  app_line=$(grep "user app on" "$SECRETS_DIR/users.acl")
  [[ "$app_line" != *"+@all"* ]]
}

@test "ACL healthcheck user is restricted to +ping only" {
  bash "$SCRIPT"
  hc_line=$(grep "user healthcheck on" "$SECRETS_DIR/users.acl")
  [[ "$hc_line" == *"+ping"* ]]
  # Must NOT have install-level commands
  [[ "$hc_line" != *"+@all"* ]]
  [[ "$hc_line" != *"+ts.add"* ]]
}

@test "ACL insight user has only read-only ts commands" {
  bash "$SCRIPT"
  insight_line=$(grep "user insight on" "$SECRETS_DIR/users.acl")
  [[ "$insight_line" == *"+ts.get"* ]]
  [[ "$insight_line" == *"+ts.range"* ]]
  # Must NOT have write commands
  [[ "$insight_line" != *"+ts.add"* ]]
  [[ "$insight_line" != *"+@all"* ]]
}

@test "ACL passwords are stored as SHA-256 hashes not plaintext" {
  bash "$SCRIPT"
  # Redis ACL uses #<hex64> for hashed passwords
  grep -qE "user admin on #[0-9a-f]{64}" "$SECRETS_DIR/users.acl"
}

@test "ACL admin hash matches expected SHA-256 of adminpassword" {
  bash "$SCRIPT"
  expected=$(printf '%s' 'adminpassword' | sha256sum | awk '{print $1}')
  grep -q "#${expected}" "$SECRETS_DIR/users.acl"
}

# ---------------------------------------------------------------------------
# File permissions — security-critical
# ---------------------------------------------------------------------------

@test "secrets directory has 700 permissions" {
  bash "$SCRIPT"
  perms=$(stat -c '%a' "$SECRETS_DIR")
  [ "$perms" = "700" ]
}

@test "all secret files have 444 permissions" {
  bash "$SCRIPT"
  local bad=0
  while IFS= read -r -d '' f; do
    perms=$(stat -c '%a' "$f")
    if [ "$perms" != "444" ]; then
      echo "wrong perms $perms on $f" >&2
      bad=1
    fi
  done < <(find "$SECRETS_DIR" -type f -print0)
  [ "$bad" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Missing env var handling
# ---------------------------------------------------------------------------

@test "fails non-zero when REDIS_CERT_CA is unset" {
  unset REDIS_CERT_CA
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "error message names the missing variable" {
  export REDIS_CERT_CA=""
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" =~ REDIS_CERT_CA ]]
}

@test "fails when REDIS_KEY_SERVER is unset" {
  unset REDIS_KEY_SERVER
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "fails when REDIS_PASSWORD_ADMIN is unset" {
  unset REDIS_PASSWORD_ADMIN
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "fails when REDIS_HASH_ADMIN is unset" {
  unset REDIS_HASH_ADMIN
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "fails when REDIS_HASH_ADMIN is empty string" {
  export REDIS_HASH_ADMIN=""
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "error message names the hash variable when empty" {
  export REDIS_HASH_INSIGHT=""
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" =~ REDIS_HASH_INSIGHT ]]
}

# ---------------------------------------------------------------------------
# Sanity-check: decode_to rejects near-empty payloads
# ---------------------------------------------------------------------------

@test "fails when decoded cert is only whitespace" {
  # printf '\n' | base64 = 'Cg==' (1 byte); decode_to guards against this.
  export REDIS_CERT_CA
  REDIS_CERT_CA=$(printf '\n' | base64 -w0)
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# Idempotency: re-run cleans up prior state
# ---------------------------------------------------------------------------

@test "removes stale files from a previous run before writing new ones" {
  bash "$SCRIPT"
  touch "$SECRETS_DIR/stale_file"
  # Script should rm -rf SECRETS_DIR at startup
  bash "$SCRIPT"
  [ ! -f "$SECRETS_DIR/stale_file" ]
}

# ---------------------------------------------------------------------------
# SECRETS_DIR override
# ---------------------------------------------------------------------------

@test "respects SECRETS_DIR override" {
  custom=$(mktemp -d)
  SECRETS_DIR="$custom" run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$custom/ca.pem" ]
  rm -rf "$custom"
}

# ---------------------------------------------------------------------------
# Success message
# ---------------------------------------------------------------------------

@test "prints materialized confirmation on success" {
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"materialized"* || "$output" == *"Secrets"* ]]
}
