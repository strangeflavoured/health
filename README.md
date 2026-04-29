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

## Run tests
```bash
docker compose run --rm --build test-runner
```
## Build documentation

```bash
docker compose run --rm --build docs-compiler
```
To compile the pdf documentation (requires `make`) run
```bash
make -C docs/build/latex
```

The documentation can be found in `docs/build/html/index.html` and `docs/build/latex/healthanalyser.pdf`

-------

## Set up Redis Stack
Add `.env` file to repo root:
```bash
touch .env && chmod 600 .env
```
Add the following contents:
```ini
REDIS_HOST=127.0.0.1
REDIS_PORT=6380
REDIS_INSIGHT_PORT=5540
REDIS_DB=0
REDIS_CERTS_DIR=secrets
REDIS_SERVER_CERT=redis.pem
REDIS_SERVER_KEY=redis.key
REDIS_CA_CERT=rootCA.pem
REDIS_APP_CERT=app-cert.pem
REDIS_APP_KEY=app.key
```

Install `openssl` and `mkcert`:
```bash
sudo apt install mkcert openssl
mkcert -install
```

Generate a safe redis password and encryption key phrases for infrastructure and app and append them to `.env`:
```bash
echo "REDIS_PASSWORD=$(openssl rand -base64 32)\n" >> .env
echo "KEY_PASSPHRASE_INFRA=$(openssl rand -base64 32)\n" >> .env
echo "KEY_PASSPHRASE_APP=$(openssl rand -base64 32)\n" >> .env
```

Generate TLS certificates for infrastructure and app client:

```bash
bash scripts/generate_certificate.sh $(mkcert -CAROOT)
bash scripts/generate_certificate.sh --client app $(mkcert -CAROOT)
```
Use the previously generated passphrases when prompted.

Add path to CA certificate to `.env`:
```bash
echo "CA_PATH=$(mkcert -CAROOT)/rootCA.pem" >> .env
```


Finally start up [docker container](docs/CHEATSHEET.md):
```bash
docker compose up -d redis redisinsight
```
Set up RedisInsight by accessing `http://<REDIS_HOST>:<REDIS_INSIGHT_PORT>` in your browser:
Set up TLS and create a new client certificate for `RedisInsightUI`.

--------

## Importer
[Export Apple Health data](https://support.apple.com/guide/iphone/share-your-health-data-iph5ede58c3d/ios)
and save the `export.zip` you obtain in `data` directory.
Create an `output` directory within project root with permissions for container:
```bash
mkdir -p ./output && sudo chown 1000:1000 ./output
```

Run `import_to_redis.py` in sandbox to upload the data to Redis:
```bash
docker compose run --rm --build sandbox import_to_redis.py
```

----------

## Development
### Install dev requirements
```bash
pip install --require-hashes -r requirements-dev.txt
```

Before a commit, run pre-commit and fix issues:
```bash
pre-commit run
```
