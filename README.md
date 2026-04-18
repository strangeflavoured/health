# Getting started
## Prerequisites
### Importer
Requires [Python3.11](https://www.python.org/downloads/release/python-31115/) (including `venv` and `pip`).

## Set up virtual environments
Clone repository and cd into it:
```bash
git clone git@github.com:strangeflavoured/health.git && cd "$(basename "$_" .git)"
```

Create virtual environments for import and analysis:
```bash
python3.11 -m venv .venv3.11 --prompt health-import
python3.12 -m venv .venv3.12 --prompt health-analysis
```

Activate each environment, update pip and install requirements:
```bash
source .venv3.11/bin/activate
pip install --upgrade pip
pip install --require-hashes -r requirements-import.txt
deactivate
```
```bash
source .venv3.12/bin/activate
pip install --upgrade pip
pip install --require-hashes -r requirements-analysis.txt
deactivate
```

## Set up Redis Stack
First [install docker compose](https://docs.docker.com/compose/install).
Pull the latest redis-stack-server:
```bash
docker pull redis/redis-stack-server:latest && docker pull redis/redisinsight:latest
```
Then add a `.env` file to the root directory which contains the following variables:
```dotenv
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
```dotenv
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
Enter the importer environment:
```bash
source .venv3.11/bin/activate
```

## Development
### Install dev requirements
```bash
pip install --require-hashes -r requirements-dev.txt
```

Before a commit, run pre-commit and fix issues:
```bash
pre-commit run
```
