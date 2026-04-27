# Getting started

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
To compile the pdf documentation run
```bash
make -C docs/build/latex
```

The documentation can be found in `docs/build/html/index.html` and `docs/build/latex/healthanalyser.pdf`

-------

## Set up Redis Stack
First [install docker compose](https://docs.docker.com/compose/install).
Pull the latest redis-stack-server:
```bash
docker pull redis/redis-stack-server:latest && docker pull redis/redisinsight:latest
```
Then add a `.env` file to the root directory which contains the following variables:
```ini
REDIS_HOST=127.0.0.1
REDIS_PORT=6380
REDIS_INSIGHT_PORT=5540
REDIS_DB=0
```
Generate a safe password and add it to `.env`
```bash
echo "REDIS_PASSWORD=$(openssl rand -base64 32)" >> .env
```
`.env` can be protected from unauthorised access by running

```bash
chmod 600 .env
```
Generate [TLS certificates](docs/REDIS_TLS.md) and add the directory and file names to `.env`, similar to this:
```ini
REDIS_CERTS_DIR=~/.redis-certs
REDIS_SERVER_CERT=redis.pem
REDIS_SERVER_KEY=redis.key
REDIS_CA_CERT=rootCA.pem
REDIS_CLIENT_CERT=client-cert.pem
REDIS_CLIENT_KEY=client.key
```
Finally start up [docker container](docs/CHEATSHEET.md).
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
