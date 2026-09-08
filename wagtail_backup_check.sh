#!/bin/bash
# Checks whether each locally-drifted media/ directory is fully, byte-for-
# byte backed up in pCloud before it's safe to delete and replace with the
# symlink git actually tracks at that path (see .gitignore's comment on
# org-data/*/*/media/* and README_symlink.md).
#
# Compares EVERY file by sha256 checksum, not just filenames/counts/dates --
# a filename+count match can still hide truncated or edited content, and
# the whole point here is 100% certainty before anything gets deleted.
#
# This does not delete or modify anything. It only reports.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PCLOUD_BASE="/home/john/pCloudDrive/strollopia_org_data"

# The known-drifted media directories (relative to this repo's root) --
# each one is currently a real directory locally but a git-tracked symlink
# pointing into pCloud. Add more paths here if others turn up later.
PAIRS=(
  "org-data/climate-stories.strollopia.com/climate-map/media"
  "org-data/kentville.strollopia.com/business-map/media"
  "org-data/kentville.strollopia.com/mural-map/media"
  "org-data/valleyartmap.strollopia.com/art-map/media"
)

BOLD=$(tput bold 2>/dev/null || true)
RESET=$(tput sgr0 2>/dev/null || true)
GREEN=$(tput setaf 2 2>/dev/null || true)
RED=$(tput setaf 1 2>/dev/null || true)
YELLOW=$(tput setaf 3 2>/dev/null || true)

overall_safe=true

relative_file_list() {
  # $1 = directory. Prints sorted relative paths ("./a/b.jpg" style), or
  # nothing if the directory doesn't exist.
  local dir="$1"
  [ -d "$dir" ] || return 0
  # comm requires strict byte-order sorting to compare correctly -- a
  # locale-aware sort (the default) can order filenames differently than
  # comm expects whenever names contain spaces, apostrophes, or mixed
  # case, which silently produces wrong only-in-X results without the
  # LC_ALL=C pin (comm itself warns "not in sorted order" when this bites).
  ( cd "$dir" && find . -type f | LC_ALL=C sort )
}

sha256_for() {
  # $1 = directory, $2 = relative path within it. Prints just the hash.
  ( cd "$1" && sha256sum "$2" 2>/dev/null | awk '{print $1}' )
}

for pair in "${PAIRS[@]}"; do
  local_path="$SCRIPT_DIR/$pair"
  pcloud_path="$PCLOUD_BASE/$pair"

  echo
  echo "${BOLD}=== $pair ===${RESET}"

  if [ ! -d "$local_path" ]; then
    echo "  local directory does not exist -- nothing to check (already resolved?)"
    continue
  fi
  if [ ! -d "$pcloud_path" ]; then
    echo "  ${RED}pCloud path does not exist: $pcloud_path${RESET}"
    echo "  ${RED}NOT SAFE -- pCloud has nothing to fall back on for this directory.${RESET}"
    overall_safe=false
    continue
  fi

  local_files=$(relative_file_list "$local_path")
  pcloud_files=$(relative_file_list "$pcloud_path")

  only_local=$(comm -23 <(echo "$local_files") <(echo "$pcloud_files"))
  only_pcloud=$(comm -13 <(echo "$local_files") <(echo "$pcloud_files"))
  in_both=$(comm -12 <(echo "$local_files") <(echo "$pcloud_files"))

  local_count=$(echo "$local_files" | grep -c . || true)
  pcloud_count=$(echo "$pcloud_files" | grep -c . || true)
  echo "  local: $local_count files   pCloud: $pcloud_count files"

  mismatches=""
  checked=0
  if [ -n "$in_both" ]; then
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      checked=$((checked + 1))
      local_hash=$(sha256_for "$local_path" "$rel")
      pcloud_hash=$(sha256_for "$pcloud_path" "$rel")
      if [ "$local_hash" != "$pcloud_hash" ]; then
        mismatches="${mismatches}${rel}\n"
      fi
    done <<< "$in_both"
  fi
  echo "  checked $checked shared files by sha256"

  problem=false

  if [ -n "$only_local" ]; then
    problem=true
    echo "  ${RED}only in local (would be LOST if replaced by a symlink):${RESET}"
    echo "$only_local" | sed 's/^/    /'
  fi

  if [ -n "$mismatches" ]; then
    problem=true
    echo "  ${RED}content differs between local and pCloud (same name, different bytes):${RESET}"
    printf '%b' "$mismatches" | sed 's/^/    /'
  fi

  if [ -n "$only_pcloud" ]; then
    echo "  ${YELLOW}only in pCloud (fine -- no local data at risk):${RESET}"
    echo "$only_pcloud" | sed 's/^/    /'
  fi

  if [ "$problem" = true ]; then
    overall_safe=false
    echo "  ${RED}NOT SAFE to replace yet.${RESET}"
  else
    echo "  ${GREEN}100% match -- every local file exists in pCloud with identical content.${RESET}"
    echo "  ${GREEN}Safe to run: rm -rf \"$local_path\" && ln -s \"$pcloud_path\" \"$local_path\"${RESET}"
  fi
done

echo
if [ "$overall_safe" = true ]; then
  echo "${GREEN}${BOLD}All checked directories are fully backed up in pCloud.${RESET}"
  exit 0
else
  echo "${RED}${BOLD}At least one directory is NOT fully backed up -- do not delete it yet.${RESET}"
  exit 1
fi
