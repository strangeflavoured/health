#!/bin/sh
set -e

SECRETS="/run/secrets"

ENCRYPTED_KEY="${SECRETS}/server.key"
DECRYPTED_KEY="/run/secrets_rw/redis.key"

# /run/secrets is a tmpfs mount — never touches disk
echo "Decrypting Redis server key..."
openssl pkcs8 \
    -in "$ENCRYPTED_KEY" \
    -out "$DECRYPTED_KEY" \
    -passin "file:$SECRETS/key_passphrase_infra"
chmod 600 "$DECRYPTED_KEY"

# read secrets
ADMIN_PASSWORD="$(cat $SECRETS/admin_password)"
APP_PASSWORD="$(cat $SECRETS/app_password)"
INSIGHT_PASSWORD="$(cat $SECRETS/insight_password)"
HEALTHCHECK_PASSWORD="$(cat $SECRETS/healthcheck_password)"

# Generate ACL file from environment variables at runtime
ACL_FILE="/run/secrets_rw/users.acl"
printf 'user default off nopass -@all\n' > "$ACL_FILE"
printf 'user admin on >%s ~* &* +@all\n' "$ADMIN_PASSWORD" >> "$ACL_FILE"
printf 'user app on >%s ~HK* resetchannels +ts.add +multi +exec +ping +client|setname +client|getname\n' "$APP_PASSWORD" >> "$ACL_FILE"
printf 'user insight on >%s ~HK* resetchannels +ts.get +ts.range +ts.revrange +ts.mget +ts.mrange +ts.mrevrange +ts.info +ts.queryindex +ping +info +client|setname +client|getname +scan +type +dbsize\n' "$INSIGHT_PASSWORD" >> "$ACL_FILE"
printf 'user healthcheck on >%s resetchannels +ping\n' "$HEALTHCHECK_PASSWORD" >> "$ACL_FILE"
chmod 600 "$ACL_FILE"

# Unset password variables immediately after use
unset ADMIN_PASSWORD APP_PASSWORD INSIGHT_PASSWORD HEALTHCHECK_PASSWORD


export REDIS_ARGS="--tls-port 6380
  --port 0
  --tls-auth-clients yes
  --tls-ca-cert-file $SECRETS/ca.pem
  --tls-cert-file $SECRETS/server.pem
  --tls-key-file $DECRYPTED_KEY
  --appendonly yes
  --maxmemory 900mb
  --maxmemory-policy allkeys-lfu
  --loglevel notice
  --aclfile $ACL_FILE"

# Hand off to the original entrypoint
exec /entrypoint.sh
