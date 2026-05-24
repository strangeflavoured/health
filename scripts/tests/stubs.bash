#!/usr/bin/env bash
# stubs.bash — shared stub-factory helpers for bats test suites.
#
# Source this file in your bats setup():
#   source "$(dirname "$BATS_TEST_FILENAME")/stubs.bash"
#
# All stubs are written to $STUB_DIR, which MUST be set before calling
# any helper here and placed first on $PATH.

# ---------------------------------------------------------------------------
# Generic stub factories
# ---------------------------------------------------------------------------

# stub_noop NAME   — creates $STUB_DIR/NAME that exits 0 silently.
stub_noop() {
  local name="$1"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$STUB_DIR/$name"
  chmod +x "$STUB_DIR/$name"
}

# stub_exit NAME CODE   — creates a stub that exits with CODE.
stub_exit() {
  local name="$1"
  local code="$2"
  printf '#!/usr/bin/env bash\nexit %s\n' "$code" > "$STUB_DIR/$name"
  chmod +x "$STUB_DIR/$name"
}

# stub_record NAME LOG_FILE   — creates a stub that appends its full argv to
# LOG_FILE and exits 0.  Useful for asserting what commands were invoked.
stub_record() {
  local name="$1"
  local log="$2"
  cat > "$STUB_DIR/$name" <<EOF
#!/usr/bin/env bash
echo "$name \$*" >> "$log"
exit 0
EOF
  chmod +x "$STUB_DIR/$name"
}

# ---------------------------------------------------------------------------
# docker stub
# ---------------------------------------------------------------------------

create_docker_stub() {
  local log="${DOCKER_CALL_LOG:-/tmp/docker_calls.log}"
  cat > "$STUB_DIR/docker" <<EOF
#!/usr/bin/env bash
echo "docker \$*" >> "$log"
exit 0
EOF
  chmod +x "$STUB_DIR/docker"
}

# ---------------------------------------------------------------------------
# pass(1) stub — returns canned secret values
# ---------------------------------------------------------------------------

create_pass_stub() {
  cat > "$STUB_DIR/pass" <<'EOF'
#!/usr/bin/env bash
key="${*: -1}"
case "$key" in
  health/redis/certs/ca.pem)           printf 'FAKE-CA-CERT'          ;;
  health/redis/certs/server.pem)       printf 'FAKE-SERVER-CERT'      ;;
  health/redis/certs/healthcheck.pem)  printf 'FAKE-HEALTHCHECK-CERT' ;;
  health/redis/certs/redisinsight.pem) printf 'FAKE-INSIGHT-CERT'     ;;
  health/redis/certs/app.pem)          printf 'FAKE-APP-CERT'         ;;
  health/redis/keys/server.key)        printf 'FAKE-SERVER-KEY'       ;;
  health/redis/keys/healthcheck.key)   printf 'FAKE-HEALTHCHECK-KEY'  ;;
  health/redis/keys/redisinsight.key)  printf 'FAKE-INSIGHT-KEY'      ;;
  health/redis/keys/app.key)           printf 'FAKE-APP-KEY'          ;;
  health/redis/passwords/admin)        printf 'adminpassword'         ;;
  health/redis/passwords/healthcheck)  printf 'healthpassword'        ;;
  health/redis/passwords/insight)      printf 'insightpassword'       ;;
  health/redis/passwords/app)          printf 'apppassword'           ;;
  *) printf 'UNKNOWN-SECRET-%s' "$key"; exit 1 ;;
esac
EOF
  chmod +x "$STUB_DIR/pass"
}

# ---------------------------------------------------------------------------
# CI secret environment helpers
# ---------------------------------------------------------------------------

# Populates all REDIS_* env vars with valid base64-encoded fake values.
export_fake_ci_secrets() {
  local pw_admin="adminpassword"
  local pw_app="apppassword"
  local pw_hc="healthpassword"
  local pw_insight="insightpassword"

  REDIS_CERT_CA=$(printf 'fake-ca-cert' | base64 -w0)
  REDIS_CERT_SERVER=$(printf 'fake-server-cert' | base64 -w0)
  REDIS_CERT_HEALTHCHECK=$(printf 'fake-healthcheck-cert' | base64 -w0)
  REDIS_CERT_REDISINSIGHT=$(printf 'fake-redisinsight-cert' | base64 -w0)
  REDIS_CERT_APP=$(printf 'fake-app-cert' | base64 -w0)
  export REDIS_CERT_CA REDIS_CERT_SERVER REDIS_CERT_HEALTHCHECK \
         REDIS_CERT_REDISINSIGHT REDIS_CERT_APP

  REDIS_KEY_SERVER=$(printf 'fake-server-key' | base64 -w0)
  REDIS_KEY_HEALTHCHECK=$(printf 'fake-healthcheck-key' | base64 -w0)
  REDIS_KEY_REDISINSIGHT=$(printf 'fake-redisinsight-key' | base64 -w0)
  REDIS_KEY_APP=$(printf 'fake-app-key' | base64 -w0)
  export REDIS_KEY_SERVER REDIS_KEY_HEALTHCHECK REDIS_KEY_REDISINSIGHT \
         REDIS_KEY_APP

  REDIS_PASSWORD_ADMIN=$(printf '%s' "$pw_admin" | base64 -w0)
  REDIS_PASSWORD_APP=$(printf '%s' "$pw_app" | base64 -w0)
  REDIS_PASSWORD_HEALTHCHECK=$(printf '%s' "$pw_hc" | base64 -w0)
  REDIS_PASSWORD_INSIGHT=$(printf '%s' "$pw_insight" | base64 -w0)
  export REDIS_PASSWORD_ADMIN REDIS_PASSWORD_APP REDIS_PASSWORD_HEALTHCHECK \
         REDIS_PASSWORD_INSIGHT

  # Hashes are SHA-256 hex strings, then base64-encoded.
  REDIS_HASH_ADMIN=$(printf '%s' "$pw_admin" | sha256sum | awk '{print $1}' \
                     | tr -d '\n' | base64 -w0)
  REDIS_HASH_APP=$(printf '%s' "$pw_app" | sha256sum | awk '{print $1}' \
                   | tr -d '\n' | base64 -w0)
  REDIS_HASH_HEALTHCHECK=$(printf '%s' "$pw_hc" | sha256sum | awk '{print $1}' \
                            | tr -d '\n' | base64 -w0)
  REDIS_HASH_INSIGHT=$(printf '%s' "$pw_insight" | sha256sum | awk '{print $1}' \
                       | tr -d '\n' | base64 -w0)
  export REDIS_HASH_ADMIN REDIS_HASH_APP REDIS_HASH_HEALTHCHECK REDIS_HASH_INSIGHT
}
