# Cutting a release

Releases are tagged with **signed, annotated** git tags. The tag is created and
signed **locally** with the maintainer's GPG key — the signing key never reaches
a CI runner. The automated release pipeline (`.github/workflows/release.yml`)
handles everything after the tag exists: provenance attestation, SBOM, VEX, and
the docs deploy.

> Signing the tag and attesting the artifacts are two separate controls. The
> signed tag attests _"this commit is the release point, authored by the
> maintainer"_; the Sigstore build-provenance attestation (produced in CI)
> attests _"these artifacts came from this build."_ Both are required.

## One-time setup (GPG signing)

Requires a GPG key whose user-ID email matches a **verified email on the
maintainer's GitHub account** — otherwise GitHub renders the signature as
"Unverified".

Identify an existing key, or generate one:

```sh
# Existing key — note the long key ID (the part after the slash):
gpg --list-secret-keys --keyid-format=long
#   sec   rsa4096/AB12CD34EF56AB78 ...
#                  ^^^^^^^^^^^^^^^^ key ID

# Or generate a new one (RSA 4096 is broadly compatible):
gpg --full-generate-key
```

Point git at the key and sign all annotated tags by default:

```sh
git config --global user.signingkey AB12CD34EF56AB78
git config --global tag.gpgsign true
git config --global user.email "the-email-on-the-key@example.com"

# Required so the passphrase prompt works in a terminal session.
# Add this to your shell rc file (e.g. ~/.bashrc, ~/.zshrc):
export GPG_TTY=$(tty)
```

Export the public key and upload it to GitHub:

```sh
gpg --armor --export AB12CD34EF56AB78
```

- Copy the entire block, including the `-----BEGIN/END PGP PUBLIC KEY BLOCK-----`
  lines.
- GitHub → Settings → SSH and GPG keys → **New GPG key** → paste → Add.

> A key that signs but isn't uploaded will still pass `git tag -v` locally, but
> the signature is unverifiable for anyone else and won't show "Verified" on
> GitHub — which defeats the point of the control. If a tag shows "Unverified"
> after upload, the cause is almost always that the key's UID email is not a
> verified email on the GitHub account.

## Per-release procedure

Do **not** let the GitHub release UI create the tag — it creates a lightweight,
unsigned tag. Instead, create the signed tag first and point the release at it.

```sh
# 1. Create the signed, annotated tag (-s signs; tag.gpgsign=true also covers -a)
git tag -s vX.Y.Z -m "Release vX.Y.Z"

# 2. Verify it locally before pushing
git tag -v vX.Y.Z          # should print a good GPG signature

# 3. Push the tag
git push origin vX.Y.Z

# 4. Create the release from the EXISTING tag.
#    --verify-tag refuses to proceed if the tag is missing or invalid,
#    which guards against accidentally creating a release on an unsigned tag.
gh release create vX.Y.Z --verify-tag --generate-notes
```

Publishing the release fires the `release` workflow, which then runs the
provenance/SBOM/VEX/docs steps automatically.

## Re-signing an existing unsigned tag

A lightweight tag (e.g. one created by the GitHub UI) cannot be signed in place;
it is replaced with a signed annotated tag pointing at the **same commit**.
Capture the original commit first so the tag does not silently move to `HEAD`:

```sh
COMMIT=$(git rev-list -n 1 vX.Y.Z)
git tag -s vX.Y.Z "$COMMIT" -f -m "Release vX.Y.Z"
git tag -v vX.Y.Z
git push -f origin vX.Y.Z
```

Force-moving rewrites the tag ref. For this single-maintainer project that is
acceptable, but do it deliberately: anyone who already fetched the old tag must
re-fetch with `--force`, and any existing release object will then point at the
re-signed tag (same commit, so no practical change).

## Verifying a released tag

```sh
git fetch --tags
git tag -v vX.Y.Z
```

Confirm tags are annotated (signed), not lightweight. `objecttype` should be
`tag`, never `commit`:

```sh
git for-each-ref refs/tags --format='%(refname:short) %(objecttype)'
```

## Notes

- **Artifact verification** for released assets uses the build-provenance
  attestation, not a checksum file:
  `gh attestation verify <asset> --repo strangeflavoured/health`.
