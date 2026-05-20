#!/usr/bin/env bats
# Tests for generate_certificates.sh
#
# Requires: mkcert, openssl
# These tests create a real local CA and issue real certificates so that
# chain-verification and permission assertions are meaningful.
#
# Security focus:
#   * Key files must be 600 (private keys must never be world-readable).
#   * Output directory must be 700.
#   * Certificate chain must validate against the issuing CA.
#
# Safety focus:
#   * --client mode without a name must exit non-zero.
#   * Infra mode without rootCA.pem must exit non-zero.
#   * Extra arguments in --client mode must exit non-zero.

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/generate_certificates.sh"

setup_file() {
  command -v mkcert  &>/dev/null || skip "mkcert not available"
  command -v openssl &>/dev/null || skip "openssl not available"

  export TEST_CA_DIR
  TEST_CA_DIR="$(mktemp -d)"
  export CAROOT="$TEST_CA_DIR"
  # Install a local CA into TEST_CA_DIR (no-op if already present).
  mkcert -install 2>/dev/null || true
}

teardown_file() {
  rm -rf "$TEST_CA_DIR"
}

setup() {
  OUT_DIR="$(mktemp -d)"
  export OUT_DIR
}

teardown() {
  rm -rf "$OUT_DIR"
}

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

@test "exits non-zero when CA directory has no rootCA.pem" {
  empty=$(mktemp -d)
  run bash "$SCRIPT" "$empty" "$OUT_DIR"
  rm -rf "$empty"
  [ "$status" -ne 0 ]
  [[ "$output" =~ "No CA certificate" ]]
}

@test "--client without a name argument exits non-zero" {
  run bash "$SCRIPT" --client
  [ "$status" -ne 0 ]
}

@test "--client with empty name exits non-zero" {
  run bash "$SCRIPT" --client "" "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -ne 0 ]
}

@test "--client with all-whitespace name exits non-zero" {
  run bash "$SCRIPT" --client "   " "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -ne 0 ]
}

@test "--client with extra unexpected arguments exits non-zero" {
  run bash "$SCRIPT" --client myapp "$TEST_CA_DIR" "$OUT_DIR" extra_arg
  [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# Infra mode
# ---------------------------------------------------------------------------

@test "infra mode creates server certificate (redis.pem)" {
  run bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/redis.pem" ]
}

@test "infra mode creates server key (redis.key)" {
  run bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/redis.key" ]
}

@test "infra mode creates redisinsight client certificate" {
  run bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/redisinsight-cert.pem" ]
}

@test "infra mode creates healthcheck client certificate" {
  run bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/healthcheck-cert.pem" ]
}

@test "infra mode server cert contains 127.0.0.1 SAN by default" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  text=$(openssl x509 -in "$OUT_DIR/redis.pem" -noout -text 2>/dev/null)
  [[ "$text" == *"127.0.0.1"* ]]
}

@test "infra mode server cert contains localhost SAN" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  text=$(openssl x509 -in "$OUT_DIR/redis.pem" -noout -text 2>/dev/null)
  [[ "$text" == *"localhost"* ]]
}

@test "custom IP SAN argument is included in server cert" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR" 192.168.100.1
  text=$(openssl x509 -in "$OUT_DIR/redis.pem" -noout -text 2>/dev/null)
  [[ "$text" == *"192.168.100.1"* ]]
}

# ---------------------------------------------------------------------------
# Client mode
# ---------------------------------------------------------------------------

@test "--client mode creates <name>-cert.pem" {
  run bash "$SCRIPT" --client testapp "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/testapp-cert.pem" ]
}

@test "--client mode creates <name>.key" {
  run bash "$SCRIPT" --client testapp "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/testapp.key" ]
}

@test "--client mode strips spaces from CN for filenames" {
  run bash "$SCRIPT" --client "my app" "$TEST_CA_DIR" "$OUT_DIR"
  [ "$status" -eq 0 ]
  [ -f "$OUT_DIR/myapp-cert.pem" ]
}

@test "--client mode does NOT create a server certificate" {
  bash "$SCRIPT" --client testapp "$TEST_CA_DIR" "$OUT_DIR"
  [ ! -f "$OUT_DIR/redis.pem" ]
  [ ! -f "$OUT_DIR/redis.key" ]
}

# ---------------------------------------------------------------------------
# File permissions — security-critical
# ---------------------------------------------------------------------------

@test "private key files have 600 permissions (infra mode)" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  local bad=0
  while IFS= read -r -d '' keyfile; do
    perms=$(stat -c '%a' "$keyfile")
    if [ "$perms" != "600" ]; then
      echo "wrong perms $perms on $keyfile" >&2
      bad=1
    fi
  done < <(find "$OUT_DIR" -name "*.key" -print0)
  [ "$bad" -eq 0 ]
}

@test "private key file has 600 permissions (client mode)" {
  bash "$SCRIPT" --client cli "$TEST_CA_DIR" "$OUT_DIR"
  perms=$(stat -c '%a' "$OUT_DIR/cli.key")
  [ "$perms" = "600" ]
}

@test "output directory has 700 permissions" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  perms=$(stat -c '%a' "$OUT_DIR")
  [ "$perms" = "700" ]
}

# ---------------------------------------------------------------------------
# Certificate chain verification
# ---------------------------------------------------------------------------

@test "server certificate chains to the CA" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  run openssl verify -CAfile "$TEST_CA_DIR/rootCA.pem" "$OUT_DIR/redis.pem"
  [ "$status" -eq 0 ]
}

@test "healthcheck cert chains to the CA" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  run openssl verify -CAfile "$TEST_CA_DIR/rootCA.pem" "$OUT_DIR/healthcheck-cert.pem"
  [ "$status" -eq 0 ]
}

@test "redisinsight cert chains to the CA" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  run openssl verify -CAfile "$TEST_CA_DIR/rootCA.pem" "$OUT_DIR/redisinsight-cert.pem"
  [ "$status" -eq 0 ]
}

@test "client cert chains to the CA" {
  bash "$SCRIPT" --client myapp "$TEST_CA_DIR" "$OUT_DIR"
  run openssl verify -CAfile "$TEST_CA_DIR/rootCA.pem" "$OUT_DIR/myapp-cert.pem"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Idempotency: valid certs must not be regenerated
# ---------------------------------------------------------------------------

@test "does not regenerate a still-valid server cert on second run" {
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  mtime_before=$(stat -c '%Y' "$OUT_DIR/redis.pem")
  sleep 1
  bash "$SCRIPT" "$TEST_CA_DIR" "$OUT_DIR"
  mtime_after=$(stat -c '%Y' "$OUT_DIR/redis.pem")
  [ "$mtime_before" -eq "$mtime_after" ]
}
