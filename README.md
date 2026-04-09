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
