#!/usr/bin/env bash
# Checks that the commit message contains a valid Signed-off-by trailer.
# Run automatically as a pre-commit commit-msg hook.

msg_file="$1"
commit_msg=$(cat "$msg_file")

# Skip merge commits
if echo "$commit_msg" | grep -q "^Merge "; then
  exit 0
fi

if ! echo "$commit_msg" | grep -qE "^Signed-off-by: .+ <.+@.+>$"; then
  echo "ERROR: Missing 'Signed-off-by' trailer." >&2
  echo "Add it with:  git commit -s" >&2
  echo "Or configure permanently:  git config --global format.signoff true" >&2
  exit 1
fi
