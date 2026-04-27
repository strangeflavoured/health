# dockerfile for docs-compiler
FROM python:3.14.0-slim-trixie

# Install system dependencies
RUN apt-get update && apt-get install --yes --no-install-recommends make && apt-get dist-upgrade --yes -V && rm -rf /var/lib/apt/lists/*

# create user
RUN useradd --create-home --uid 1000 health
USER health
WORKDIR /home/health/

# Install requirements
COPY --chown=health:health ./docs/requirements.txt .
ENV PATH="/home/health/.local/bin:$PATH"
RUN pip install --user --upgrade pip
RUN pip install --user --require-hashes --no-cache-dir -r requirements.txt

COPY --chown=health:health ./src ./src
COPY --chown=health:health ./docs ./docs

ENTRYPOINT ["make", "-C", "docs", "clean", "html", "latex"]
