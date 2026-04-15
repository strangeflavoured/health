# Getting started
The data import of this project relies on [apple_health_exporter](https://github.com/mganjoo/apple-health-exporter)
which requires Python 3.11. For the analysis infrastructure I will be using Python 3.12, which requires a separation
of requirements and environments for this project.

## Prerequisites

Make sure you have Python 3.11  and 3.12 installed:
```bash
sudo apt install python3.11 & sudo apt install python 3.12
```

Make sure you have pip installed:
```bash
sudo apt install pip
```

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
docker pull redis/redis-stack-server:latest
```
Then add a `.env` file to the root directory which contains the following variables:
```dotenv
REDIS_HOST=127.0.0.1
REDIS_PORT=6380
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
REDIS_TLS_CA_CERT=rootCA.pem
REDIS_CLIENT_CERT=client-cert.pem
REDIS_CLIENT_KEY=client.key
```
Finally start up [docker container](docs/CHEATSHEET.md).

## Import

Enter the import environment:
```bash
source .venv3.11/bin/activate
```

## Analysis

```bash
source .venv3.12/bin/activate
```

## Development
### Install dev requirements

```bash
pip install --require-hashes -r requirements-dev.txt
```

Before a commit, run the following tools and fix issues:
```bash
ruff check && pre-commit run && vulture
```
