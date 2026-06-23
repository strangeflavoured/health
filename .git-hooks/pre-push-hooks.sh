#!/usr/bin/env bash
set -uo pipefail

ref="${PRE_COMMIT_TO_REF:-HEAD}"

declare -A skip_set=()
if [ -n "${SKIP:-}" ]; then
  IFS=',' read -ra _ids <<< "$SKIP"
  for _id in "${_ids[@]}"; do
    _id="${_id#"${_id%%[![:space:]]*}"}"
    _id="${_id%"${_id##*[![:space:]]}"}"
    [ -n "$_id" ] && skip_set["$_id"]=1
  done
fi
skip() { [ -n "${skip_set[$1]:-}" ]; }

tmp=$(mktemp -d)
trap 'git worktree remove --force "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
git worktree add --detach --quiet "$tmp" "$ref"
cd "$tmp" || exit 1

tests_rc=0 mypy_rc=0 signatures_rc=0
tests_pid="" mypy_pid="" signatures_pid=""

uv sync --all-groups

if skip tests; then echo "SKIP tests" >&2
else .git-hooks/test-hook.sh "$@" & tests_pid=$!; fi

if skip mypy; then echo "SKIP mypy" >&2
else uv run --frozen mypy & mypy_pid=$!; fi

if skip signatures; then echo "SKIP signatures" >&2
else .git-hooks/verify-signatures.sh "$@" & signatures_pid=$!; fi

[ -n "$tests_pid" ]      && { wait "$tests_pid";      tests_rc=$?; }
[ -n "$mypy_pid" ]       && { wait "$mypy_pid";       mypy_rc=$?; }
[ -n "$signatures_pid" ] && { wait "$signatures_pid"; signatures_rc=$?; }

[ "$tests_rc" -eq 0 ] && [ "$mypy_rc" -eq 0 ] && [ "$signatures_rc" -eq 0 ]
