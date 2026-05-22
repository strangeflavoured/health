#!/usr/bin/env bash
# re-compile all requirements.txt files
set -euo pipefail

source .venv/bin/activate

if ! command -v uv &>/dev/null; then
  echo "error: uv is required but not found." >&2
  echo "Install: pip install --require-hashes -r requirements-dev.txt" >&2
  exit 1
fi

IN_FILES=("pip-requirements.in" "requirements-dev.in" "src/importer/requirements.in" "src/requirements.in" "backend/requirements/base.in" "backend/requirements/tests.in" "docs/requirements.in" "tests/requirements.in")

_discover_in_files() {
  git ls-files -- '*.in' \
    | grep -E '(^|/)(requirements|[^/]+-requirements|requirements-[^/]+)\.in$|(^|/)requirements/[^/]+\.in$' \
    | sort -u
}

_verify_file_list() {
  local discovered explicit only_in_list only_on_disk
  discovered=$(_discover_in_files)
  explicit=$(printf '%s\n' "${IN_FILES[@]}" | sort -u)

  only_in_list=$(comm -23 <(echo "$explicit") <(echo "$discovered"))
  only_on_disk=$(comm -13 <(echo "$explicit") <(echo "$discovered"))

  if [[ -n "$only_in_list" || -n "$only_on_disk" ]]; then
    echo "ERROR: Explicit .in file list is out of sync with the filesystem." >&2
    [[ -n "$only_in_list" ]]  && echo "$only_in_list"  | sed 's/^/  in list, not on disk: /' >&2
    [[ -n "$only_on_disk" ]]  && echo "$only_on_disk"  | sed 's/^/  on disk, not in list: /' >&2
    echo "" >&2
    echo "Update the IN_FILES array in $(basename "$0") to match." >&2
    return 1
  fi
}

compile_one() {
  local in_file="$1"
  local out_file="${in_file%.in}.txt"
  local log

  echo -n "  compiling $in_file... "
  if ! log=$(uv pip compile "$in_file" \
      --allow-unsafe \
      --generate-hashes \
      --output-file "$out_file" \
      --quiet \
      --strip-extras \
      2>&1); then
    echo "FAILED: ${in_file}" >&2
    echo "$log" >&2
    return 1
  fi
  echo "ok"
}

_verify_file_list || exit 1

failed=0
for in_file in "${IN_FILES[@]}"; do
  compile_one "$in_file" || failed=1
done

deactivate

exit "$failed"
