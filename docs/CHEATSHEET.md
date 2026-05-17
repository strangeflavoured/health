# Docker/Redis Stack Cheatsheet

## Build Container

```bash
docker compose build [--no-cache] redis redisinsight
```

## Start Container

Instead of using `docker compose up` use the `compose-wrapper`:

```bash
./scripts/compose-wrapper.sh up [-d] redis redisinsight
```

This wrapper injects `pass` secrets to docker via the host tmpfs `/dev/shm`.
To remove all secrets from the tmpfs run

```bash
./scripts/compose-wrapper.sh down
```

## Container status/logs

```bash
docker compose ps
docker compose logs -f redis
```

## Connect to Redis-CLI

With `redis` container running and healthy:

```bash
docker compose exec redis sh -c 'redis-cli \
  --tls \
  --cacert /run/secrets/ca.pem \
  --cert /run/secrets/app.pem \
  --key /run/secrets/app.key \
  --user app \
  -a "$(cat /run/secrets/app_password)" \
  --no-auth-warning \
  -p 6380'
```

## Check resource usage

```bash
docker stats health-redis
```

## Check health

```bash
docker inspect --format='{{json .State.Health}}' $(docker compose ps -q redis) | jq
```

## Container stoppen / entfernen

```bash
./scripts/compose-wrapper.sh down redis redisinsight          # stoppt Container, Volume bleibt erhalten
./scripts/compose-wrapper.sh down -v redis redisinsight       # stoppt Container UND löscht das Volume (Datenverlust!)
```

---

## Backup

Create a `dump.rdb` via the redis-cli:

```bash
docker compose exec redis sh -c 'redis-cli \
  --tls \
  --cacert /run/secrets/ca.pem \
  --cert /run/secrets/app.pem \
  --key /run/secrets/app.key \
  --user app \
  -a "$(cat /run/secrets/app_password)" \
  --no-auth-warning \
  -p 6380 \
  BGSAVE'
```

Find the mount point via

```bash
docker volume inspect health_redis-data
```

and copy the file via

```bash
sudo cp /mount/point/path/dump.rdb /backup/path/dump_name.rdb
```
