#!/usr/bin/env bash
# re-compile all requirements.txt files
set -euo pipefail

source .venv/bin/activate

IN_FILES=("pip-requirements" "requirements-dev" "src/importer/requirements" "src/requirements" "backend/requirements/base" "backend/requirements/tests" "docs/requirements" "tests/requirements")

_discover_in_files() {
  git ls-files -- '*.in' \
    | grep -E '(^|/)(requirements|[^/]+-requirements|requirements-[^/]+)\.in$|/requirements/[^/]+\.in$' \
    | sed 's/\.in$//' \
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

_verify_file_list || exit 1

for in_file in "${IN_FILES[@]}"; do
  pip-compile --allow-unsafe --generate-hashes --strip-extras --output-file="${in_file}".txt "${in_file}".in
done

deactivate
