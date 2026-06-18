#!/usr/bin/env bash
set -uo pipefail

ref="${PRE_COMMIT_TO_REF:-HEAD}"

tmp=$(mktemp -d)
trap 'git worktree remove --force "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
git worktree add --detach --quiet "$tmp" "$ref"
cd "$tmp" || exit 1

uv run --frozen mypy
