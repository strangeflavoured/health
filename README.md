## Getting started

### Prerequisites

Make sure you have Python 3.11 installed:

    sudo apt install python3.11

Make sure you have pip3 installed:
```
sudo apt install pip3
```

### Set up virtual environment

Clone repository and cd into it:
```
    git clone git@github.com:strangeflavoured/health.git && cd "$(basename "$_" .git)"
```

Create a virtual environment and activate it:
```
    python3.11 -m venv .venv --prompt health && source .venv/bin/activate
```

Update pip3 and install requirements:
```
    pip3 install --upgrade pip
    pip3 install --require-hashes -r requirements.txt
```

### Set up Redis
First [install docker compose](https://docs.docker.com/compose/install). Then add a `.env` file to the root directory which contains

```
    REDIS_PASSWORD="your_super_secret_password"
```

Pull the latest redis-stack-server and run docker compose:
```
    docker pull redis/redis-stack-server:latest && docker compose up -d
```

The container can be closed with
```
    docker compose down
```

### Development tools

Install ruff and pre-commit:
```
    pip install pre-commit ruff
```

Before a commit, run ruff and pre-commit and fix code style issues:
```
    ruff check && pre-commit run
```
