# Getting started
## Prerequisites
Have the following installed:
- [git](https://git-scm.com/install/)
- [docker compose](https://docs.docker.com/compose/install/)

---------

## Download Repository
Clone repository and cd into it:
```bash
git clone git@github.com:strangeflavoured/health.git && cd "$(basename "$_" .git)"
```

## Set up Secrets & Certificates

Install `openssl` and `mkcert`:
```bash
sudo apt install mkcert openssl
mkcert -install
```

Add `.env` file to repo root:
```bash
touch .env && chmod 600 .env
```
Add the necessary contents, see [.env-example](docs/.env-example). You can find the location of the CA certificate by running
```bash
mkcert -CAROOT
```
Source `.env` to access the declared variables:
```bash
source .env
```

Generate TLS certificates for infrastructure and app client:
```bash
bash scripts/generate_certificate.sh $(mkcert -CAROOT) $REDIS_CERTS_DIR
bash scripts/generate_certificate.sh --client app $(mkcert -CAROOT) $REDIS_CERTS_DIR
```

[Set up pass](docs/pass-secrets-guide.md) and add certificates and keys:
```bash
pass insert --multiline health/redis/certs/ca.pem < "$(mkcert -CAROOT)/rootCA.pem"
pass insert --multiline health/redis/certs/server.pem < "${REDIS_CERTS_DIR}/redis.pem"
pass insert --multiline health/redis/keys/server.key < "${REDIS_CERTS_DIR}/redis.key"
pass insert --multiline health/redis/certs/healthcheck.pem < "${REDIS_CERTS_DIR}/healthcheck.pem"
pass insert --multiline health/redis/keys/healthcheck.key < "${REDIS_CERTS_DIR}/healthcheck.key"
pass insert --multiline health/redis/certs/redisinsight.pem < "${REDIS_CERTS_DIR}/redisinsight.pem"
pass insert --multiline health/redis/keys/redisinsight.key < "${REDIS_CERTS_DIR}/redisinsight.key"
pass insert --multiline health/redis/certs/app.pem < "${REDIS_CERTS_DIR}/app.pem"
pass insert --multiline health/redis/keys/app.key < "${REDIS_CERTS_DIR}/app.key"
```
Generate safe passwords for redis, healthcheck, redisinsight, and app, and add them to `pass`, e.g. using `openssl rand`:
```bash
echo -n "$(openssl rand -base64 64)" | pass insert --echo health/redis/passwords/admin
echo -n "$(openssl rand -base64 32)" | pass insert --echo health/redis/passwords/healthcheck
echo -n "$(openssl rand -base64 32)" | pass insert --echo health/redis/passwords/insight
echo -n "$(openssl rand -base64 32)" | pass insert --echo health/redis/passwords/app
```

--------

## Using docker compose
Instead of using `docker compose` directly, always run
```bash
./scripts/compose-wrapper.sh up [options] [service...]
```
so `pass` secrets are injected. Similarly, to stop the services run
```bash
./scripts/stop.sh down [service...]
```
This will remove the tmpfs. See also [docker cheatsheet](docs/CHEATSHEET.md).

----------

## Set up RedisInsight
Startup redis and redisinsight
```bash
./scripts/compose-wrapper.sh up -d redis redisinsight
```

Access `http://<REDIS_HOST>:<REDIS_INSIGHT_PORT>` in your browser, and add the database.

--------

## Run tests
```bash
./scripts/compose-wrapper.sh run --rm --build test-runner
```
## Build documentation

```bash
./scripts/compose-wrapper.sh run --rm --build docs-compiler
```
To compile the pdf documentation (requires `make`) run
```bash
make -C docs/build/latex
```

The documentation can be found in `docs/build/html/index.html` and `docs/build/latex/healthanalyser.pdf`

-----------

## Importer
[Export Apple Health data](https://support.apple.com/guide/iphone/share-your-health-data-iph5ede58c3d/ios)
and save the `export.zip` you obtain in `data` directory.
Create an `output` directory within project root with permissions for container:
```bash
mkdir -p ./output && sudo chown 1000:1000 ./output
```

Run `import_to_redis.py` in sandbox to upload the data to Redis:
```bash
./scripts/compse-wrapper.sh up -d redis
./scripts/compse-wrapper.sh build -f compose.yml sandbox
./scripts/compose-wrapper.sh run --rm sandbox import_to_redis.py
```

----------

## Development
### Build Sandbox
Build sandbox with `compose-override.yml`:
```bash
./scripts/compose-wrapper.sh build sandbox
```
### Run scripts in Sandbox
Run script without rebuilding sandbox:
```bash
./scripts/compose-wrapper.sh run --rm sandbox script_to_run.py
```
