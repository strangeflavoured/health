#!/usr/bin/env bash
# One-time generator for CI-only secrets, then upload to GitHub Actions.
# Run locally whenever you want to rotate CI credentials.
#
# Requires: openssl, gh (authenticated), base64.
set -euo pipefail

REPO=${REPO:-strangeflavoured/health}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "Generating CI secrets in $WORK..."

# --- CA ---
openssl genrsa -out "$WORK/ca.key" 4096 2>/dev/null
openssl req -x509 -new -nodes -key "$WORK/ca.key" -sha256 -days 3650 \
  -subj "/CN=health-ci-ca" \
  -out "$WORK/ca.pem" 2>/dev/null

# --- Leaf certs ---
issue_cert() {
  local name=$1
  local cn=$2
  local san=${3:-}

  openssl genrsa -out "$WORK/${name}.key.pkcs8" 2048 2>/dev/null
  # Convert to PKCS#1 (Redis-compatible)
  openssl rsa -in "$WORK/${name}.key.pkcs8" -traditional \
    -out "$WORK/${name}.key" 2>/dev/null

  local config="$WORK/${name}.cnf"
  cat > "$config" <<EOF
[req]
distinguished_name = dn
req_extensions = v3_req
prompt = no
[dn]
CN = ${cn}
[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
EOF
  if [[ -n "$san" ]]; then
    echo "subjectAltName = ${san}" >> "$config"
  fi

  openssl req -new -key "$WORK/${name}.key" -config "$config" \
    -out "$WORK/${name}.csr" 2>/dev/null

  openssl x509 -req -in "$WORK/${name}.csr" \
    -CA "$WORK/ca.pem" -CAkey "$WORK/ca.key" -CAcreateserial \
    -days 365 -sha256 -extfile "$config" -extensions v3_req \
    -out "$WORK/${name}.pem" 2>/dev/null
}

issue_cert server       "redis"        "DNS:redis,DNS:localhost,IP:127.0.0.1"
issue_cert healthcheck  "healthcheck"
issue_cert app          "app"
issue_cert redisinsight "redisinsight"

# --- Passwords ---
gen_pw() { openssl rand -base64 32 | tr -d '\n=+/' | head -c 32; }

ADMIN_PW=$(gen_pw)
APP_PW=$(gen_pw)
HEALTHCHECK_PW=$(gen_pw)
INSIGHT_PW=$(gen_pw)

# --- Upload to GitHub Actions secrets ---
set_secret_from_file() {
  local name=$1
  local path=$2
  local tmp
  tmp=$(mktemp)
  base64 < "$path" > "$tmp"          # with line wrapping — gh handles it fine
  gh secret set "$name" --repo "$REPO" < "$tmp"
  rm -f "$tmp"
  echo "  set $name"
}

set_secret() {
  local name=$1
  local value=$2
  local tmp
  tmp=$(mktemp)
  printf '%s' "$value" | base64 > "$tmp"
  gh secret set "$name" --repo "$REPO" < "$tmp"
  rm -f "$tmp"
  echo "  set $name"
}

hash_pw() { printf '%s' "$1" | sha256sum | awk '{print $1}'; }

echo "Uploading certificates..."
set_secret_from_file REDIS_CERT_CA           "$WORK/ca.pem"
set_secret_from_file REDIS_CERT_SERVER       "$WORK/server.pem"
set_secret_from_file REDIS_CERT_HEALTHCHECK  "$WORK/healthcheck.pem"
set_secret_from_file REDIS_CERT_REDISINSIGHT "$WORK/redisinsight.pem"
set_secret_from_file REDIS_CERT_APP          "$WORK/app.pem"

echo "Uploading keys..."
set_secret_from_file REDIS_KEY_SERVER       "$WORK/server.key"
set_secret_from_file REDIS_KEY_HEALTHCHECK  "$WORK/healthcheck.key"
set_secret_from_file REDIS_KEY_REDISINSIGHT "$WORK/redisinsight.key"
set_secret_from_file REDIS_KEY_APP          "$WORK/app.key"

echo "Uploading passwords..."
set_secret REDIS_PASSWORD_ADMIN       "$ADMIN_PW"
set_secret REDIS_PASSWORD_APP         "$APP_PW"
set_secret REDIS_PASSWORD_HEALTHCHECK "$HEALTHCHECK_PW"
set_secret REDIS_PASSWORD_INSIGHT     "$INSIGHT_PW"

echo "Uploading password hashes..."
set_secret REDIS_HASH_ADMIN       "$(hash_pw "$ADMIN_PW")"
set_secret REDIS_HASH_APP         "$(hash_pw "$APP_PW")"
set_secret REDIS_HASH_HEALTHCHECK "$(hash_pw "$HEALTHCHECK_PW")"
set_secret REDIS_HASH_INSIGHT     "$(hash_pw "$INSIGHT_PW")"

echo "Done."
