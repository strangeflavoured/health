# syntax=docker/dockerfile:1.27@sha256:bde3983e9c939224420ddaf6b784cc30e09b035a4dea01f581230c50809f372e
FROM bats/bats:1.14.0@sha256:5322b877351fda0cc435de8c6116de7d0a2ec79d7c680132a0ef329a633bc66f

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
