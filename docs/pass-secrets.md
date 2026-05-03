# Secrets Management with `pass`

## Set up pass

### 1.1 Install dependencies

```bash
sudo apt install gnupg pass
```

### 1.2 Generate a GPG key

```bash
gpg --full-generate-key
```

When prompted:
- Key type: `(1) RSA and RSA`
- Key size: `4096`
- Expiry: `0` (no expiry) or `2y` for better hygiene
- Name and email: your real details — used to identify the key
- Passphrase: strong, memorable — this protects everything

Find your key fingerprint:

```bash
gpg --list-keys
# Note the long hex string, or use your email in subsequent commands
```

### 1.3 Configure GPG agent

Ensure the agent can prompt for the passphrase in a terminal (required for SSH sessions and headless environments):

```bash
mkdir -p ~/.gnupg
echo "pinentry-mode loopback" >> ~/.gnupg/gpg.conf
echo "allow-loopback-pinentry" >> ~/.gnupg/gpg-agent.conf
gpgconf --reload gpg-agent
echo 'export GPG_TTY=$(tty)' >> ~/.bashrc
source ~/.bashrc
```

### 1.4 Initialise the pass store

```bash
pass init user.name@example.com
```

This creates `~/.password-store/` and records which GPG key encrypts the store.

### 1.5 Insert secrets

**Passwords and passphrases** are single-line values. Use `--echo` to insert them non-interactively:

```bash
echo -n "super_secret_password"       | pass insert --echo health/redis/passwords/my_super_secret_password
```

`-n` on `echo` prevents a trailing newline — important because Redis would treat it as part of the password. Do not use `--echo` for multi-line values.

**Private keys and certificates** are multi-line PEM files. Use `--multiline` which reads stdin until EOF and preserves all newlines exactly.

```bash
pass insert --multiline health/redis/certs/my_cert.pem           < "/path/to/my_cert.pem"
pass insert --multiline health/redis/keys/my_cert.key           < "/path/to/my_cert.key"
```

Verify passwords inserted correctly:

```bash
pass health/redis
# Should show the full tree including both passwords and certs/

pass health/redis/passwords/my_super_secret_password
# Should print the password
```

Verify PEM round-trip integrity for each key:
```bash
pass health/redis/keys/my_cert.key | openssl pkey -noout -text 2>&1 | head -5
# Should show key type and parameters, not an error

pass health/redis/certs/my_cert.pem | openssl x509 -noout -subject 2>&1
# Should show the certificate subject
```

### 1.6 Back up the GPG private key

Store the backup on an encrypted USB or in a separate password manager. Without this backup, the encrypted secrets are unrecoverable if the key is lost.

```bash
gpg --export-secret-keys --armor user.name@example.com > ~/health-gpg-private.asc
chmod 600 ~/health-gpg-private.asc
# Move this file off the machine — do not leave it here long-term
# Never commit it to git
```

Export the public key separately (safe to commit):

```bash
gpg --export --armor user.name@example.com > ~/health/gpg-public.asc
```

### 1.7 Git-back the pass store (recommended)

```bash
pass git init
pass git remote add origin git@github.com:youruser/health-secrets.git
pass git push -u origin main
```

Every subsequent `pass insert`, `pass edit`, or `pass rm` automatically commits. Push with `pass git push`.

Update `.gitignore`:

```text
# Plaintext secrets — never commit
.env

# GPG private key backup — never commit
*.asc
!gpg-public.asc
```

### 1.8 Optionally configure passwordless sudo for tmpfs

To avoid entering your sudo password on every startup, add a targeted sudoers rule:

```bash
sudo visudo -f /etc/sudoers.d/health-tmpfs
```

Add:
```
user ALL=(ALL) NOPASSWD: /bin/mount -t tmpfs *, /bin/umount /run/health-secrets, /bin/rm -rf /run/health-secrets, /bin/mkdir -p /run/health-secrets, /bin/chown * /run/health-secrets
```

---

## Day-to-Day Workflow

### Starting the stack

```bash
./scripts/compose-wrapper.sh compose -d redis
```

The GPG agent prompts for your key passphrase on the first decryption after login. Subsequent runs within the same session are served from the agent cache without re-prompting.

The start script does not automatically wipe the tmpfs on exit. The tmpfs is wiped by `./scripts/compose-wrapper.sh down` instead, or cleared automatically on reboot.

### Stopping the stack

Bring down the containers and wipe the tmpfs:

```bash
./scripts/compose-wrapper.sh down
```

Do not use `docker compose down` directly — it won't wipe the tmpfs.

### Viewing secrets

```bash
pass health/redis                      # list the full tree
pass health/redis/passwords/admin       # decrypt and print to stdout
pass -c health/redis/passwords/admin    # copy to clipboard (clears after 45s)
pass health/redis/keys/server.key     # print a key to stdout
```

### Rotating a password

```bash
echo -n "$NEW_USER_PASSWORD" | pass insert --force --echo health/redis/passwords/user
```

After rotation, restart the affected service to pick up the new value:

```bash
./scripts/compose-wrapper.sh down
./scripts/compose-wrapper up -d redis
```

If the store is git-backed, push the rotation:

```bash
pass git push
```

### Rotating a certificate or key

Use `--multiline` and redirect from the new file — never use `--echo` for PEM content:

```bash
pass insert --force --multiline health/redis/keys/cert.key < /path/to/new/cert.key
pass insert --force --multiline health/redis/certs/cert.pem < /path/to/new/cert.pem
```

Verify the round-trip before restarting:

```bash
pass health/redis/keys/server.key | openssl pkey -noout -text 2>&1 | head -5
# Should show key parameters, not an error
```

Then restart the affected service:

```bash
./scripts/compose-wrapper.sh down
./scripts/compose-wrapper up -d redis
```

### Adding a new secret

```bash
# Single-line value
echo -n "$NEW_VALUE" | pass insert --echo health/redis/new_secret

# Multi-line / PEM file
pass insert --multiline health/redis/certs/new_cert.pem < /path/to/cert.pem
```

Then:
1. Add a decryption line to `scripts/compose-wrapper.sh`: `printf '%s' "$(pass show health/redis/new_secret)" > "$SECRETS_DIR/new_secret"`
2. Add a secret mount in `compose.yml` for the affected service.
3. Update the entrypoint or application code to read from `/run/secrets/new_secret`

### Removing a secret

```bash
pass rm health/redis/old_secret
```

Then remove the corresponding mount from `compose.yml` and the decryption line from `scripts/compose-wrapper.sh`.

### Checking what's exposed

Verify nothing secret is in container environments:

```bash
docker inspect health-redis | python3 -m json.tool | grep -A 50 '"Env"'
docker exec health-redis env
```

Neither should contain passwords, passphrases, or key material.

### GPG agent session management

The agent caches your passphrase for the duration of a session. To extend the cache lifetime:

```bash
echo "default-cache-ttl 3600" >> ~/.gnupg/gpg-agent.conf    # 1 hour idle timeout
echo "max-cache-ttl 86400"    >> ~/.gnupg/gpg-agent.conf    # 24 hour maximum
gpgconf --reload gpg-agent
```

To manually clear the cache before stepping away:

```bash
gpgconf --reload gpg-agent
```

### Reboot behaviour

The tmpfs at is cleared on reboot — this is intentional. After rebooting, run `./scripts/compose-wrapper.sh` as normal; it will re-create the tmpfs and decrypt fresh from the pass store.
