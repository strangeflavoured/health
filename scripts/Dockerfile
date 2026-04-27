# dockerfile for sandbox
FROM python:3.14.0-slim-trixie

# Install system dependencies
RUN apt-get update
RUN apt-get install --no-install-recommends --yes -V wait-for-it
RUN apt-get dist-upgrade --yes -V

# create user
RUN useradd --create-home --uid 1000 health
USER health
WORKDIR /home/health/

# Install requirements
COPY --chown=health:health ../src/requirements.txt .
RUN pip install --user --upgrade pip
RUN pip install --require-hashes --no-cache-dir -r requirements.txt

COPY --chown=health:health ../src ./src
COPY --chown=health:health ./scripts .

ENTRYPOINT ["wait-for-it", "redis:6380", "--", "python3"]
CMD ["import_to_redis.py"]
