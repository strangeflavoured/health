#!/bin/bash
set -euo pipefail

umask 077

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage () {
  echo "Usage: $0 [ca-directory=.] [output-directory=./secrets] [server ip-address... (default: 127.0.0.1)]" >&2
  echo "Usage: $0 --client <client-name> [ca-directory=.] [output-directory=.]" >&2
}

# ---------------------------------------------------------------------------
# Argument parsing — determine mode first
# ---------------------------------------------------------------------------
MODE="infra"
CLIENT_CN=""
CLIENT_CN_SAFE=""

if [[ $# -gt 0 && "$1" == "--client" ]]; then
  MODE="client"
  shift
  if [[ $# -lt 1 || -z "$1" ]]; then
    echo "Error: --client requires a client name" >&2
    usage
    exit 1
  fi
  CLIENT_CN="$1"
  # Strip whitespace for filenames; mkcert does not allow whitespace in CN
  CLIENT_CN_SAFE="${CLIENT_CN//[[:space:]]/}"
  if [[ -z "$CLIENT_CN_SAFE" ]]; then
    echo "Error: client name is empty after removing whitespace" >&2
    exit 1
  fi
  shift
fi

CA_DIR="$(pwd)"
if [[ $# -gt 0 && -d "$1" ]]; then
  CA_DIR="$1"
  shift
fi

export CAROOT="$CA_DIR"

# Optional output directory — where all generated cert and key files are written
# Defaults to cwd/secrets; created if it does not exist
OUT_DIR="$(pwd)/secrets"
if [[ "$MODE" == "infra" && $# -gt 0 && ( -d "$1" || ! "$1" =~ ^[0-9] ) ]] ||
   [[ "$MODE" == "client" && $# -gt 0 ]]; then
  OUT_DIR="$1"
  shift
  mkdir -p "$OUT_DIR"
fi
chmod 700 "$OUT_DIR"

# Remaining arguments are IP SANs (infra mode only)
# If provided, they replace 127.0.0.1; localhost and redis are always included
if [[ "$MODE" == "infra" ]]; then
  FIXED_SANS=(localhost redis)
  EXTRA_IPS=("$@")
  if [[ ${#EXTRA_IPS[@]} -eq 0 ]]; then
    SERVER_SANS=(127.0.0.1 "${FIXED_SANS[@]}")
  else
    SERVER_SANS=("${EXTRA_IPS[@]}" "${FIXED_SANS[@]}")
  fi
elif [[ $# -gt 0 ]]; then
  echo "Error: unexpected arguments in --client mode: $*" >&2
  usage
  exit 1
fi

# ---------------------------------------------------------------------------
# Verify CA exists in the specified directory
# ---------------------------------------------------------------------------
if [[ ! -f "$CA_DIR/rootCA.pem" ]]; then
  echo "Error: No CA certificate found in '$CA_DIR'" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Check whether a certificate is still valid for at least 30 days
cert_valid() {
  local cert="$1"
  openssl x509 -checkend $((30 * 86400)) -noout -in "$cert" 2>/dev/null
}

# Verify a certificate chains up to the CA
verify_chain() {
  local cert="$1"
  local label="$2"
  if ! openssl verify -CAfile "$CA_DIR/rootCA.pem" "$cert" > /dev/null 2>&1; then
    echo "Error: chain verification failed for $label" >&2
    return 1
  fi
  echo "Chain verified: $label"
}

# Convert plaintext PKCS#8 (mkcert output) to encrypted PKCS#8
encrypt_key() {
  local plain_key="$1"
  local encrypted_key="$2"
  local passphrase="$3"
  openssl pkcs8 -topk8 \
    -v2 aes-256-cbc \
    -v2prf hmacWithSHA512 \
    -iter 600000 \
    -in "$plain_key" \
    -out "$encrypted_key" \
    -passout "pass:${passphrase}"
  chmod 600 "$encrypted_key"
  # Overwrite file contents before unlinking
  shred -u "$plain_key"
}

# Prompt for a passphrase with confirmation, storing result in the
# variable varname. Usage: prompt_passphrase "label" VARNAME
prompt_passphrase() {
  local label="$1"
  local varname="$2"
  local pass confirm
  read -r -s -p "Enter ${label} passphrase: " pass
  echo
  read -r -s -p "Confirm ${label} passphrase: " confirm
  echo
  if [[ "$pass" != "$confirm" ]]; then
    echo "Error: ${label} passphrases do not match" >&2
    exit 1
  fi
  # Assign to the caller's named variable
  printf -v "$varname" '%s' "$pass"
}

# Verify a passphrase decrypts an existing key — catches mismatches
# before any new keys are generated
verify_passphrase() {
  local key="$1"
  local passphrase="$2"
  if ! openssl pkey -in "$key" -passin "pass:${passphrase}" -noout 2>/dev/null; then
    echo "Error: passphrase does not match existing key '$key'" >&2
    echo "To rotate the passphrase, delete the affected .key files and re-run." >&2
    exit 1
  fi
}

# Generate a client certificate and key.
# Encrypted with the supplied passphrase, or unencrypted if passphrase is empty.
# Usage: gen_client_cert <cn> <cert_path> <key_path> <passphrase>
#
# Passing an empty passphrase produces an unencrypted key — used only for
# the healthcheck cert where redis-cli cannot supply a passphrase at runtime.
gen_client_cert() {
  local cn="$1"
  local cert="$2"
  local key="$3"
  local passphrase="$4"
  local plain_key="${key%.key}-plain.key"

  if [[ -f "$cert" ]] && cert_valid "$cert"; then
    if [[ -n "$passphrase" && -f "$key" ]]; then
      verify_passphrase "$key" "$passphrase"
    fi
    return 0
  fi

  [[ -f "$cert" ]] && echo "Certificate for '${cn}' expired or expiring soon, regenerating..."
  PLAIN_KEYS+=("$plain_key")
  mkcert -ecdsa -client -key-file "$plain_key" -cert-file "$cert" "$cn"

  if [[ -n "$passphrase" ]]; then
    encrypt_key "$plain_key" "$key" "$passphrase"
  else
    # Intentionally unencrypted — caller is responsible for ensuring this
    # is only used for minimal-privilege certs (e.g. healthcheck)
    mv "$plain_key" "$key"
    chmod 600 "$key"
  fi

  verify_chain "$cert" "client certificate (${cn})"
}

# ---------------------------------------------------------------------------
# Cleanup trap: shred any plaintext keys if the script exits unexpectedly
# Registered before any key files are created
# ---------------------------------------------------------------------------
PLAIN_KEYS=()

cleanup() {
  for f in "${PLAIN_KEYS[@]+"${PLAIN_KEYS[@]}"}"; do
    [[ -f "$f" ]] && shred -u "$f"
  done
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# INFRA MODE
# Generates: server cert, redisinsight client cert, healthcheck client cert
# All encrypted with the infrastructure passphrase (except healthcheck)
# ---------------------------------------------------------------------------
if [[ "$MODE" == "infra" ]]; then

  # Collect infrastructure passphrase
  # Shared by Redis server and RedisInsight — must match the key_passphrase
  # Swarm secret. Only prompted when at least one cert needs action.
  INFRA_KEYS=("$OUT_DIR/redis.key" "$OUT_DIR/redisinsight.key")
  NEED_INFRA_PASSPHRASE=false

  for key in "${INFRA_KEYS[@]}"; do
    [[ -f "$key" ]] && NEED_INFRA_PASSPHRASE=true && break
  done

  if [[ ! -f "$OUT_DIR/redis.pem" ]] || ! cert_valid "$OUT_DIR/redis.pem" || \
     [[ ! -f "$OUT_DIR/redisinsight-cert.pem" ]] || ! cert_valid "$OUT_DIR/redisinsight-cert.pem" || \
     [[ ! -f "$OUT_DIR/healthcheck-cert.pem" ]] || ! cert_valid "$OUT_DIR/healthcheck-cert.pem"; then
    NEED_INFRA_PASSPHRASE=true
  fi

  INFRA_PASSPHRASE=""
  if [[ "$NEED_INFRA_PASSPHRASE" == true ]]; then
    echo "Infrastructure passphrase — shared by Redis server and RedisInsight."
    echo "This passphrase must match the key_passphrase Swarm secret."
    prompt_passphrase "infrastructure" INFRA_PASSPHRASE

    # Validate against any existing infra keys before generating anything new
    for key in "${INFRA_KEYS[@]}"; do
      [[ -f "$key" ]] && verify_passphrase "$key" "$INFRA_PASSPHRASE"
    done
  fi

  # Server certificate — encrypted with infra passphrase
  if [[ ! -f "$OUT_DIR/redis.pem" ]] || ! cert_valid "$OUT_DIR/redis.pem"; then
    [[ -f "$OUT_DIR/redis.pem" ]] && echo "Server certificate expired or expiring soon, regenerating..."
    PLAIN_KEYS+=("$OUT_DIR/redis-plain.key")
    mkcert -ecdsa -key-file "$OUT_DIR/redis-plain.key" -cert-file "$OUT_DIR/redis.pem" "${SERVER_SANS[@]}"
    encrypt_key "$OUT_DIR/redis-plain.key" "$OUT_DIR/redis.key" "$INFRA_PASSPHRASE"
    echo "Server SANs: ${SERVER_SANS[*]}"
    verify_chain "$OUT_DIR/redis.pem" "server certificate"
  fi

  # RedisInsight client certificate — encrypted with infra passphrase
  gen_client_cert \
    "redisinsight" \
    "$OUT_DIR/redisinsight-cert.pem" \
    "$OUT_DIR/redisinsight.key" \
    "$INFRA_PASSPHRASE"

  # Healthcheck client certificate — intentionally unencrypted
  # redis-cli has no mechanism to supply a passphrase at runtime
  gen_client_cert \
    "healthcheck" \
    "$OUT_DIR/healthcheck-cert.pem" \
    "$OUT_DIR/healthcheck.key" \
    ""

# ---------------------------------------------------------------------------
# CLIENT MODE
# Generates a single named client certificate encrypted with the client's
# own passphrase, independent of the infrastructure passphrase
# ---------------------------------------------------------------------------
elif [[ "$MODE" == "client" ]]; then

  CLIENT_CERT="$OUT_DIR/${CLIENT_CN_SAFE}-cert.pem"
  CLIENT_KEY="$OUT_DIR/${CLIENT_CN_SAFE}.key"
  CLIENT_PASSPHRASE=""

  echo "Client passphrase for '${CLIENT_CN_SAFE}' — managed independently by this user."
  prompt_passphrase "client (${CLIENT_CN_SAFE})" CLIENT_PASSPHRASE

  gen_client_cert \
    "$CLIENT_CN_SAFE" \
    "$CLIENT_CERT" \
    "$CLIENT_KEY" \
    "$CLIENT_PASSPHRASE"
fi
