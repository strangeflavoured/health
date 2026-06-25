#!/usr/bin/env bash
#
# pre-push hook: reject the push unless every commit being pushed is signed by
# a trusted key. Two accepted sources:
#   1. A key listed in the repo-tracked SSH allowed-signers file
#      (.github/allowed_signers), verified via git's %G? against that file.
#   2. GitHub's web-flow GPG key (.github/web-flow.gpg) for commits made in the
#      GitHub web UI (web edits, merges, GitHub Advanced Security autofix
#      suggestions), which are GPG-signed by GitHub as "GitHub <noreply@github.com>".
#
# Both trust roots are repo-tracked; verification does not depend on any
# contributor's personal git/gpg config. Requires git >= 2.34; the GitHub path
# additionally requires gpg.
#
# Driven by pre-commit's pre-push stage (PRE_COMMIT_FROM_REF / PRE_COMMIT_TO_REF).
#
set -euo pipefail

root=$(git rev-parse --show-toplevel) || exit 1
allowed="$root/.github/allowed_signers"
webflow="$root/.github/web-flow.gpg"
rel="${allowed#"$root"/}"

if [ ! -f "$allowed" ]; then
    echo "error: allowed-signers file not found at $rel" >&2
    exit 1
fi

# Accept a GitHub web-flow commit iff its committer is GitHub's web-flow identity
# AND its GPG signature verifies against the pinned web-flow key, checked in a
# throwaway keyring so the user's real keyring is never touched or relied upon.
verify_github_webflow() {
    local commit="$1"
    [ -f "$webflow" ] || return 1
    [ "$(git show --no-patch --format='%ce' "$commit")" = "noreply@github.com" ] || return 1
    command -v gpg >/dev/null 2>&1 || return 1
    local tmp rc=0
    tmp=$(mktemp -d)
    GNUPGHOME="$tmp" gpg --quiet --import "$webflow" >/dev/null 2>&1 || true
    GNUPGHOME="$tmp" git -c gpg.program=gpg verify-commit "$commit" >/dev/null 2>&1 || rc=$?
    rm -rf "$tmp"
    return "$rc"
}

zero=$(git hash-object --stdin </dev/null | tr '0-9a-f' '0')
from="${PRE_COMMIT_FROM_REF:-}"
to="${PRE_COMMIT_TO_REF:-}"

if [ -z "$to" ] || [ "$to" = "$zero" ]; then
    exit 0
fi

if [ -z "$from" ] || [ "$from" = "$zero" ]; then
    mapfile -t commits < <(git rev-list "$to" --not --remotes)
else
    mapfile -t commits < <(git rev-list "$from..$to")
fi

[ "${#commits[@]}" -eq 0 ] && exit 0

status=0
for commit in "${commits[@]}"; do
    [ -z "$commit" ] && continue
    sig=$(git -c gpg.ssh.allowedSignersFile="$allowed" show --no-patch --format='%G?' "$commit")
    if [ "$sig" = "G" ]; then
        continue          # good SSH signature from a listed signer
    fi
    if verify_github_webflow "$commit"; then
        continue          # valid GitHub web-flow GPG signature
    fi
    short=$(git rev-parse --short "$commit")
    subject=$(git show --no-patch --format='%s' "$commit")
    echo "  x ${short} [${sig}] ${subject}"
    status=1
done

if [ "$status" -ne 0 ]; then
    cat >&2 <<EOF

Push rejected: every commit must be signed by a key in ${rel}, or be a
GitHub web-flow commit signed by .github/web-flow.gpg.

Status codes: G=good  U=valid/unknown signer  B=bad  E=cannot check  N=none
EOF
fi

exit "$status"
