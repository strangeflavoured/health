#!/usr/bin/env bash
# Materialize secrets in CI from base64-encoded environment variables.
set -euo pipefail

SECRETS_DIR=${SECRETS_DIR:-/dev/shm/health-secrets-$(id -u)}
export SECRETS_DIR

rm -rf "$SECRETS_DIR"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Helper: decode a base64-encoded env var into a file.
# Fails explicitly when the variable is unset/empty OR when the decoded
# content is zero or one byte (guards against `echo '' | base64` → '\n').
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
  local size
  size=$(wc -c < "$path")
  if [[ "$size" -le 1 ]]; then
    echo "Error: decoded content of $var is empty or whitespace-only (${size} byte(s))" >&2
    exit 1
  fi
}

# Helper: decode a base64-encoded env var into a shell variable (stdout).
# Applies the same emptiness and whitespace guards as decode_to so that
# REDIS_HASH_* values go through identical validation as certs/keys/passwords.
decode_var() {
  local var=$1
  local value="${!var}"
  if [[ -z "$value" ]]; then
    echo "Error: env var $var is empty" >&2
    exit 1
  fi
  local decoded
  decoded=$(printf '%s' "$value" | base64 -d) || {
    echo "Error: failed to decode $var" >&2
    exit 1
  }
  if [[ -z "$decoded" ]]; then
    echo "Error: decoded content of $var is empty" >&2
    exit 1
  fi
  printf '%s' "$decoded"
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

# ACL FILE — decode and validate all hash values upfront so any missing or
# malformed variable produces an explicit, named error before the ACL is written.
# Previously these were expanded inline inside $(...) subshells, bypassing the
# decode_to emptiness guard entirely.
HASH_ADMIN=$(decode_var REDIS_HASH_ADMIN)
HASH_APP=$(decode_var REDIS_HASH_APP)
HASH_INSIGHT=$(decode_var REDIS_HASH_INSIGHT)
HASH_HEALTHCHECK=$(decode_var REDIS_HASH_HEALTHCHECK)

ACL_FILE="$SECRETS_DIR/users.acl"
{
  printf 'user default off nopass -@all\n'
  printf 'user admin on #%s ~* &* +@all\n' \
    "$HASH_ADMIN"
  printf 'user app on #%s ~HK* resetchannels +ts.add +multi +exec +ping +client|setname +client|getname\n' \
    "$HASH_APP"
  printf 'user insight on #%s ~HK* resetchannels +ts.get +ts.range +ts.revrange +ts.mget +ts.mrange +ts.mrevrange +ts.info +ts.queryindex +ping +info +client|setname +client|getname +scan +type +dbsize\n' \
    "$HASH_INSIGHT"
  printf 'user healthcheck on #%s resetchannels +ping\n' \
    "$HASH_HEALTHCHECK"
} > "$ACL_FILE"

chmod 444 "$SECRETS_DIR"/*

# Sanity check
for f in "$SECRETS_DIR"/*; do
  [[ -s "$f" ]] || { echo "Error: $f is empty" >&2; exit 1; }
done

echo "Secrets materialized in $SECRETS_DIR"
