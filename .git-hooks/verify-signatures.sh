#!/usr/bin/env bash
#
# pre-push hook: reject the push unless every commit being pushed is signed by
# a key listed in the repo-tracked allowed-signers file. Verification is pinned
# to that in-repo file via `git -c gpg.ssh.allowedSignersFile=...`, so it is
# independent of each contributor's global git config.
#
# Driven by pre-commit's pre-push stage, which exports PRE_COMMIT_FROM_REF
# (remote tip) and PRE_COMMIT_TO_REF (local tip). Requires git >= 2.34.
#
# Git auto-detects the signature type (SSH vs PGP) from the commit's signature
# block, so gpg.format does not need to be set on the verifying machine.
#
set -euo pipefail

root=$(git rev-parse --show-toplevel) || exit 1
allowed="$root/.github/allowed_signers"
rel="${allowed#"$root"/}"

if [ ! -f "$allowed" ]; then
    echo "error: allowed-signers file not found at $rel" >&2
    exit 1
fi

zero=$(git hash-object --stdin </dev/null | tr '0-9a-f' '0')
from="${PRE_COMMIT_FROM_REF:-}"
to="${PRE_COMMIT_TO_REF:-}"

# Branch deletion (local tip all-zero) -> nothing to verify.
if [ -z "$to" ] || [ "$to" = "$zero" ]; then
    exit 0
fi

if [ -z "$from" ] || [ "$from" = "$zero" ]; then
    # New branch: verify every commit not already on a remote.
    mapfile -t commits < <(git rev-list "$to" --not --remotes)
else
    mapfile -t commits < <(git rev-list "$from..$to")
fi

[ "${#commits[@]}" -eq 0 ] && exit 0

status=0
for commit in "${commits[@]}"; do
    [ -z "$commit" ] && continue
    sig=$(git -c gpg.ssh.allowedSignersFile="$allowed" \
              show --no-patch --format='%G?' "$commit")
    case "$sig" in
        G) ;;  # good signature from a signer listed in the repo file
        *)
            short=$(git rev-parse --short "$commit")
            subject=$(git show --no-patch --format='%s' "$commit")
            echo "  x ${short} [${sig}] ${subject}"
            status=1
            ;;
    esac
done

if [ "$status" -ne 0 ]; then
    cat >&2 <<EOF

Push rejected: every commit must be signed by a key listed in ${rel}.

Status codes: G=good  U=valid/unknown signer  B=bad  E=cannot check  N=none
A valid signature whose signer is not listed shows as E or N - the key must be
added to the repo file (through a reviewed commit), e.g.:

  printf '%s namespaces="git" %s\n' "\$(git config user.email)" \\
    "\$(cat \$(git config user.signingkey))" >> ${rel}
EOF
fi

exit "$status"
