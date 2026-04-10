##  Redis Stack Server
## Setup
### Sicheres Passwort generieren und in `.env` eintragen
```bash
echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> .env
```


### .env vor unbefugtem Zugriff schützen
```bash
chmod 600 .env
```

TLS Zertifikate generieren (siehe [REDIS_TLS.md](REDIS_TLS.md)).

## Cheatsheet
### Container starten
```bash
docker compose up -d
```

### Containerstatus/-logs
```bash
docker compose ps
docker compose logs -f redis
```

### Mit Redis-CLI verbinden
```bash
# Passwort aus .env lesen
source .env

redis-cli \
  -p 6380 \
  --tls \
  --cacert  ~/.redis-certs/rootCA.pem \
  --cert    ~/.redis-certs/client-cert.pem \
  --key     ~/.redis-certs/client.key \
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
docker compose down          # stoppt Container, Volume bleibt erhalten
docker compose down -v       # stoppt Container UND löscht das Volume (Datenverlust!)
```
