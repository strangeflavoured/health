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

# Generate a client certificate and key.
# Usage: gen_client_cert <cn> <cert_path> <key_path>
gen_client_cert() {
  local cn="$1"
  local cert="$2"
  local key="$3"

  [[ -f "$cert" ]] && echo "Certificate for '${cn}' expired or expiring soon, regenerating..."
  mkcert -ecdsa -client -key-file "$key" -cert-file "$cert" "$cn"
  chmod 600 "$key"

  verify_chain "$cert" "client certificate (${cn})"
}

# ---------------------------------------------------------------------------
# INFRA MODE
# Generates: server cert, redisinsight client cert, healthcheck client cert
# ---------------------------------------------------------------------------
if [[ "$MODE" == "infra" ]]; then

  # Server certificate
  if [[ ! -f "$OUT_DIR/redis.pem" ]] || ! cert_valid "$OUT_DIR/redis.pem"; then
    [[ -f "$OUT_DIR/redis.pem" ]] && echo "Server certificate expired or expiring soon, regenerating..."
    mkcert -ecdsa -key-file "$OUT_DIR/redis.key" -cert-file "$OUT_DIR/redis.pem" "${SERVER_SANS[@]}"
    echo "Server SANs: ${SERVER_SANS[*]}"
    verify_chain "$OUT_DIR/redis.pem" "server certificate"
  fi

  # RedisInsight client certificate
  gen_client_cert \
    "redisinsight" \
    "$OUT_DIR/redisinsight-cert.pem" \
    "$OUT_DIR/redisinsight.key"

  # Healthcheck client certificate
  gen_client_cert \
    "healthcheck" \
    "$OUT_DIR/healthcheck-cert.pem" \
    "$OUT_DIR/healthcheck.key"

# ---------------------------------------------------------------------------
# CLIENT MODE
# Generates a single named client certificate
# ---------------------------------------------------------------------------
elif [[ "$MODE" == "client" ]]; then

  CLIENT_CERT="$OUT_DIR/${CLIENT_CN_SAFE}-cert.pem"
  CLIENT_KEY="$OUT_DIR/${CLIENT_CN_SAFE}.key"

  gen_client_cert \
    "$CLIENT_CN_SAFE" \
    "$CLIENT_CERT" \
    "$CLIENT_KEY"

fi
