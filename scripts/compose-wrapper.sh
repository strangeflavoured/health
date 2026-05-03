#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR=/dev/shm/health-secrets-$(id -u)
export SECRETS_DIR

# Detect if running detached (look for -d or --detach in args)
is_detached() {
  for arg in "$@"; do
    [[ "$arg" == "-d" || "$arg" == "--detach" ]] && return 0
  done
  return 1
}

write_secrets() {
  if [[ -d "$SECRETS_DIR" ]]; then
    rm -rf "$SECRETS_DIR"
  fi
  mkdir -p "$SECRETS_DIR"
  chmod 700 "$SECRETS_DIR"
  # CERTIFICATES
  printf '%s' "$(pass show health/redis/certs/ca.pem)"       > "$SECRETS_DIR/ca.pem"
  printf '%s' "$(pass show health/redis/certs/server.pem)"       > "$SECRETS_DIR/server.pem"
  printf '%s' "$(pass show health/redis/certs/healthcheck.pem)"       > "$SECRETS_DIR/healthcheck.pem"
  printf '%s' "$(pass show health/redis/certs/redisinsight.pem)"       > "$SECRETS_DIR/redisinsight.pem"
  printf '%s' "$(pass show health/redis/certs/app.pem)"       > "$SECRETS_DIR/app.pem"
  # KEYS
  printf '%s' "$(pass show health/redis/keys/server.key)"      > "$SECRETS_DIR/server.key"
  printf '%s' "$(pass show health/redis/keys/healthcheck.key)"     > "$SECRETS_DIR/healthcheck.key"
  printf '%s' "$(pass show health/redis/keys/redisinsight.key)"      > "$SECRETS_DIR/redisinsight.key"
  printf '%s' "$(pass show health/redis/keys/app.key)"      > "$SECRETS_DIR/app.key"
  # PASSWORDS
  printf '%s' "$(pass show health/redis/passwords/admin)"       > "$SECRETS_DIR/admin_password"
  printf '%s' "$(pass show health/redis/passwords/healthcheck)" > "$SECRETS_DIR/healthcheck_password"
  printf '%s' "$(pass show health/redis/passwords/insight)"     > "$SECRETS_DIR/insight_password"
  printf '%s' "$(pass show health/redis/passwords/app)"         > "$SECRETS_DIR/app_password"

  ACL_FILE="$SECRETS_DIR/users.acl"
  printf 'user default off nopass -@all\n' > "$ACL_FILE"
  printf 'user admin on #%s ~* &* +@all\n' \
    "$(pass show health/redis/passwords/admin | tr -d '\n' | sha256sum | awk '{print $1}')" \
    >> "$ACL_FILE"
  printf 'user app on #%s ~HK* resetchannels +ts.add +multi +exec +ping +client|setname +client|getname\n' \
    "$(pass show health/redis/passwords/app | tr -d '\n' | sha256sum | awk '{print $1}')" \
    >> "$ACL_FILE"
  printf 'user insight on #%s ~HK* resetchannels +ts.get +ts.range +ts.revrange +ts.mget +ts.mrange +ts.mrevrange +ts.info +ts.queryindex +ping +info +client|setname +client|getname +scan +type +dbsize\n' \
    "$(pass show health/redis/passwords/insight | tr -d '\n' | sha256sum | awk '{print $1}')" \
    >> "$ACL_FILE"
  printf 'user healthcheck on #%s resetchannels +ping\n' \
    "$(pass show health/redis/passwords/healthcheck | tr -d '\n' | sha256sum | awk '{print $1}')" \
    >> "$ACL_FILE"

  chmod 400 "$SECRETS_DIR"/*

  # Sanity check — fail fast if any secret is empty
  for f in "$SECRETS_DIR"/*; do
    [[ -s "$f" ]] || { echo "Error: $f is empty"; exit 1; }
  done
}

cleanup_secrets() {
  rm -rf "$SECRETS_DIR"
}

case "${1:-}" in
  up)
    write_secrets

    if is_detached "$@"; then
      # Detached: don't clean up on exit, container needs the files
      docker compose "$@"
      cat <<EOF

================================================================
Containers started in detached mode.
Secrets are kept at: $SECRETS_DIR

⚠️  Do NOT run 'docker compose down' directly.
   Use './$(basename "$0") down' instead to clean up secrets.
================================================================
EOF
    else
      # Foreground: trap cleanup so Ctrl+C / exit removes secrets
      trap cleanup_secrets EXIT INT TERM
      docker compose "$@"
    fi
    ;;

  down)
    docker compose "$@"
    cleanup_secrets
    echo "Secrets cleaned up from $SECRETS_DIR"
    ;;

  *)
    # Pass through any other compose command unchanged (logs, ps, exec, etc.)
    docker compose "$@"
    ;;
esac
