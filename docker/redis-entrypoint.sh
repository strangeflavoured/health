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

# Generate ACL file from environment variables at runtime
ACL_FILE="/run/secrets/users.acl"
printf 'user default off nopass -@all\n' > "$ACL_FILE"
printf 'user admin on >%s ~* &* +@all\n' "$ADMIN_PASSWORD" >> "$ACL_FILE"
printf 'user app on >%s ~HK* resetchannels +ts.add +multi +exec +ping +client|setname +client|getname\n' "$APP_PASSWORD" >> "$ACL_FILE"
printf 'user insight on >%s ~HK* resetchannels +ts.get +ts.range +ts.revrange +ts.mget +ts.mrange +ts.mrevrange +ts.info +ts.queryindex +ping +info +client|setname +client|getname +scan +type +dbsize\n' "$INSIGHT_PASSWORD" >> "$ACL_FILE"
printf 'user healthcheck on >%s resetchannels +ping\n' "$HEALTHCHECK_PASSWORD" >> "$ACL_FILE"
chmod 600 "$ACL_FILE"

# Repoint the key path in REDIS_ARGS to the decrypted location
REDIS_ARGS="$(echo "$REDIS_ARGS" | sed "s|/certs/${REDIS_SERVER_KEY}|${DECRYPTED_KEY}|g") --aclfile ${ACL_FILE}"
export REDIS_ARGS

# Hand off to the original entrypoint
exec /entrypoint.sh
