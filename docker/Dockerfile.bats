# syntax=docker/dockerfile:1.25@sha256:0adf442eae370b6087e08edc7c50b552d80ddf261576f4ebd6421006b2461f12
FROM bats/bats:1.13.0@sha256:6e4b9369468b7f3fd8f402ac6cc8ea7b2e4903eae28d08785f31a0245eb51a44

# install system dependencies
RUN apk add --no-cache util-linux openssl git curl

RUN git clone --depth=1 --branch v0.3.0 https://github.com/bats-core/bats-support /usr/local/lib/bats-support \
 && git clone --depth=1 --branch v0.3.0 https://github.com/bats-core/bats-assert  /usr/local/lib/bats-assert

RUN curl -fsSL "https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64" \
    -o /usr/local/bin/mkcert \
 && echo "6d31c65b03972c6dc4a14ab429f2928300518b26503f58723e532d1b0a3bbb52  /usr/local/bin/mkcert" \
    | sha256sum -c \
 && chmod +x /usr/local/bin/mkcert
ENV BATS_LIB_PATH=/usr/local/lib/node_modules

# create user
RUN adduser -D -u 1000 health
USER health
WORKDIR /home/health/

COPY --chown=health:health ./scripts ./scripts

ENTRYPOINT ["bats", "--jobs", "4", "--no-parallelize-within-files"]
CMD ["/home/health/scripts/tests"]
