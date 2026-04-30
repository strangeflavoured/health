#!/bin/sh
set -e

ENCRYPTED_KEY="/certs/${REDIS_SERVER_KEY}"
DECRYPTED_KEY="/run/secrets/redis.key"

# /run/secrets is a tmpfs mount — never touches disk
echo "Decrypting Redis server key..."
openssl pkcs8 \
    -in "$ENCRYPTED_KEY" \
    -out "$DECRYPTED_KEY" \
    -passin "pass:${REDIS_KEY_PASSPHRASE}"
chmod 600 "$DECRYPTED_KEY"

# Repoint the key path in REDIS_ARGS to the decrypted location
REDIS_ARGS="$(echo "$REDIS_ARGS" | sed "s|/certs/${REDIS_SERVER_KEY}|${DECRYPTED_KEY}|g")"
export REDIS_ARGS

# Hand off to the original entrypoint
exec /entrypoint.sh
