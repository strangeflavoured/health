## Setup TLS for Redis
How to generate the TLS certificates and keys to startup [docker](../compose.yml).
### Install mkcert (Linux)
```bash
sudo apt install mkcert
mkcert -install          # installs the CA into system + browser trust stores
```
This creates the certificate `rootCA.pem` and the private key `rootCA-key.pem`.
Their location can be found with `mkcert -CAROOT`.

> [!CAUTION]
> Never ever share or commit your private key `rootCA-key.pem`!

### Generate server certificate
Generate this for your machine (`127.0.0.1` and `localhost` here). If you run Redis on
a different machine, replace `127.0.0.1` and `localhost` accordingly, and adapt `.env`.
Convert key with `openssl` because Redis can't handle `PKCS#8` keys.
```bash
mkdir -p ~/.redis-certs && cd ~/.redis-certs
mkcert --key-file redis-key.pem --cert-file redis.pem 127.0.0.1 localhost
openssl pkcs8 -in  redis-key.pem -out redis.key -nocrypt
# Output:
#   redis.pem        ← server certificate
#   redis.key        ← server private key
```

### Generate client certificate
Convert key with `openssl` because Redis can't handle `PKCS#8` keys. Replace the user name.
```bash
mkcert -client -key-file client-key.pem -cert-file client-cert.pem "User Name"
openssl pkcs8 -in  client-key.pem -out client.key -nocrypt
# Output:
#   client-cert.pem   ← client certificate
#   client.key        ← client private key
```

### Verify the chain is correct before doing anything else
```bash
openssl verify -CAfile $(mkcert -CAROOT)/rootCA.pem redis.pem
# Out:
# redis.pem: OK

openssl verify -CAfile $(mkcert -CAROOT)/rootCA.pem client-cert.pem
# Out:
# client-cert.pem: OK
```

Copy your root certificate to `~/.redis-certs` so it can be mounted to Redis in `compose.yml`:
```bash
cp $(mkcert -CAROOT)/rootCA.pem rootCA.pem
```

Your `~/.redis-certs` directory should now contain:
```
rootCA.pem         ← CA certificate  (share with clients)
redis.pem          ← server certificate
redis.key          ← server private key  (stays on the server / in compose)
client-cert.pem    ← client certificate  (used by app)
client.key         ← client private key  (used by app)
```

If you change any of the certificate and/or key names adapt `comopose.yml` accordingly.
