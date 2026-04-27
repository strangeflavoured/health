##  Docker/Redis Stack Cheatsheet
### Container starten
```bash
docker compose up -d redis redisinsight
```

### Containerstatus/-logs
```bash
docker compose ps
docker compose logs -f redis
```

### Mit Redis-CLI verbinden
```bash
# read redis environment variables
source .env

redis-cli \
  -p ${REDIS_PORT} \
  --tls \
  --cacert  ${REDIS_CERTS_DIR}/${REDIS_CA_CERT} \
  --cert    ${REDIS_CERTS_DIR}/${REDIS_CLIENT_CERT} \
  --key     ${REDIS_CERTS_DIR}/${REDIS_CLIENT_KEY} \
  -a "$REDIS_PASSWORD" \
  --no-auth-warning
```

### Ressourcen-Verbrauch überwachen
```bash
docker stats health-redis
```

### Healthcheck-Status prüfen
```bash
docker inspect --format='{{.State.Health.Status}}' health-redis
```

### Container stoppen / entfernen
```bash
docker compose down redis redisinsight          # stoppt Container, Volume bleibt erhalten
docker compose down -v redis redisinsight       # stoppt Container UND löscht das Volume (Datenverlust!)
```
--------------
### Backup
Create a `dump.rdb` via the redis-cli:
```bash
# read redis environment variables
source .env

redis-cli \
  -p ${REDIS_PORT} \
  --tls \
  --cacert  ${REDIS_CERTS_DIR}/${REDIS_CA_CERT} \
  --cert    ${REDIS_CERTS_DIR}/${REDIS_CLIENT_CERT} \
  --key     ${REDIS_CERTS_DIR}/${REDIS_CLIENT_KEY} \
  -a "$REDIS_PASSWORD" \
  --no-auth-warning \
  BGSAVE
```
Find the mount point via
```bash
docker volume inspect health_redis-data
```
and copy the file via
```bash
sudo cp /mount/point/path/dump.rdb /backup/path/dump_name.rdb
```
