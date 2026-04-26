# dockerfile for sandbox
FROM python:3.12.13-slim-trixie

# Install system dependencies
RUN apt-get update
RUN apt-get dist-upgrade --yes -V

# create user
RUN useradd --create-home --uid 1000 health
USER health
WORKDIR /home/health/

# Install requirements
COPY --chown=health:health ../tests/requirements.txt .
RUN pip install --user --upgrade pip
RUN pip install --require-hashes --no-cache-dir -r requirements.txt

COPY --chown=health:health ../src ./src
COPY --chown=health:health ../tests .

ENTRYPOINT ["python3", "-m", "pytest"]
