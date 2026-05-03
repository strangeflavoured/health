#!/usr/bin/env bash
# Materialize secrets in CI from base64-encoded environment variables.
set -euo pipefail

SECRETS_DIR=${SECRETS_DIR:-/dev/shm/health-secrets-$(id -u)}
export SECRETS_DIR

rm -rf "$SECRETS_DIR"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Helper: decode a base64-encoded env var into a file
decode_to() {
  local var=$1
  local path=$2
  local value="${!var}"
  if [[ -z "$value" ]]; then
    echo "Error: env var $var is empty" >&2
    exit 1
  fi
  printf '%s' "$value" | base64 -d > "$path" || {
    echo "Error: failed to decode $var" >&2
    exit 1
  }
}

# CERTIFICATES
decode_to REDIS_CERT_CA           "$SECRETS_DIR/ca.pem"
decode_to REDIS_CERT_SERVER       "$SECRETS_DIR/server.pem"
decode_to REDIS_CERT_HEALTHCHECK  "$SECRETS_DIR/healthcheck.pem"
decode_to REDIS_CERT_REDISINSIGHT "$SECRETS_DIR/redisinsight.pem"
decode_to REDIS_CERT_APP          "$SECRETS_DIR/app.pem"

# KEYS
decode_to REDIS_KEY_SERVER        "$SECRETS_DIR/server.key"
decode_to REDIS_KEY_HEALTHCHECK   "$SECRETS_DIR/healthcheck.key"
decode_to REDIS_KEY_REDISINSIGHT  "$SECRETS_DIR/redisinsight.key"
decode_to REDIS_KEY_APP           "$SECRETS_DIR/app.key"

# PASSWORDS
decode_to REDIS_PASSWORD_ADMIN       "$SECRETS_DIR/admin_password"
decode_to REDIS_PASSWORD_APP         "$SECRETS_DIR/app_password"
decode_to REDIS_PASSWORD_HEALTHCHECK "$SECRETS_DIR/healthcheck_password"
decode_to REDIS_PASSWORD_INSIGHT     "$SECRETS_DIR/insight_password"

# ACL FILE — built from password hashes
ACL_FILE="$SECRETS_DIR/users.acl"
{
  printf 'user default off nopass -@all\n'
  printf 'user admin on #%s ~* &* +@all\n' \
    "$(printf '%s' "$REDIS_HASH_ADMIN" | base64 -d)"
  printf 'user app on #%s ~HK* resetchannels +ts.add +multi +exec +ping +client|setname +client|getname\n' \
    "$(printf '%s' "$REDIS_HASH_APP" | base64 -d)"
  printf 'user insight on #%s ~HK* resetchannels +ts.get +ts.range +ts.revrange +ts.mget +ts.mrange +ts.mrevrange +ts.info +ts.queryindex +ping +info +client|setname +client|getname +scan +type +dbsize\n' \
    "$(printf '%s' "$REDIS_HASH_INSIGHT" | base64 -d)"
  printf 'user healthcheck on #%s resetchannels +ping\n' \
    "$(printf '%s' "$REDIS_HASH_HEALTHCHECK" | base64 -d)"
} > "$ACL_FILE"

chmod 444 "$SECRETS_DIR"/*

# Sanity check
for f in "$SECRETS_DIR"/*; do
  [[ -s "$f" ]] || { echo "Error: $f is empty" >&2; exit 1; }
done

echo "Secrets materialized in $SECRETS_DIR"
