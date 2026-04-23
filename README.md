# Getting started
## Prerequisites
### Importer
Requires [Python3.12](https://www.python.org/downloads/release/python-31213/) (including `venv` and `pip`).

## Download Repository and create environment
Clone repository and cd into it:
```bash
git clone git@github.com:strangeflavoured/health.git && cd "$(basename "$_" .git)"
```

Create virtual environment:
```bash
python3.12 -m venv .venv --prompt health
```
## Build documentation
Activate the environment, update pip and install requirements:
```bash
source .venv/bin/activate
pip install --upgrade pip
pip install --require-hashes -r docs/requirements.txt
```
Compile Documentation (html and Latex):
```bash
make -C docs html
make -C docs latexpdf
```
The documentation can then be found in `docs/build/html/index.html` and `docs/build/latex/healthanalyser.pdf`

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

## Importer
Activate the environment, update pip and install requirements:
```bash
source .venv/bin/activate
pip install --upgrade pip
pip install --require-hashes -r src/requirements.txt
```
[Export Apple Health data](https://support.apple.com/guide/iphone/share-your-health-data-iph5ede58c3d/ios)
and save the `export.zip` you obtain in `data` directory. Run `import_to_redis.py` to upload the data to Redis.
## Development
### Install dev requirements
```bash
pip install --require-hashes -r requirements-dev.txt
```

Before a commit, run pre-commit and fix issues:
```bash
pre-commit run
```
