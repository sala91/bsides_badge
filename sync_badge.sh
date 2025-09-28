#!/usr/bin/env zsh
# Sync only changed files (follows symlinks) from local -> MicroPython via mpremote.
# - Tracks SHA1 of the *target* file for symlinks.
# - Persists manifest with optional link target to detect retargeting.
# - Options:
#     --dry-run     : show actions only
#     --clean       : delete files on device that were removed locally
#     --force <pat> : force (re)upload paths matching <pat> (zsh glob, e.g., "logos/*")
#     --only <pat>  : sync only files matching <pat> (e.g., "logos/*")
#     --verbose
#
# Defaults (customized for you):
#   PORT=/dev/tty.usbmodem83201
#   SRC=/Users/juurikas/Documents/GitHub/bsides_badge/software

set -euo pipefail

# ------------ Defaults ------------
PORT=/dev/tty.usbmodem83201
SRC=/Users/juurikas/Documents/GitHub/bsides_badge/software
DEST_PREFIX=":/"
MANIFEST="$SRC/.mp_sync_manifest.txt"
DRYRUN=no
CLEAN=no
VERBOSE=no
FORCE_PAT=""
ONLY_PAT=""

# ------------ Args ------------
args=("$@")
# Allow overriding first two positional args for PORT and SRC
if (( $# >= 1 )) && [[ "$1" != --* ]]; then PORT="$1"; shift; fi
if (( $# >= 1 )) && [[ "$1" != --* ]]; then SRC="$1"; shift; fi
while (( $# )); do
  case "$1" in
    --dry-run) DRYRUN=yes ;;
    --clean)   CLEAN=yes ;;
    --verbose) VERBOSE=yes ;;
    --force)   shift; FORCE_PAT="${1:-}"; [[ -z "$FORCE_PAT" ]] && { echo "--force needs a pattern"; exit 2; } ;;
    --only)    shift; ONLY_PAT="${1:-}"; [[ -z "$ONLY_PAT" ]] && { echo "--only needs a pattern"; exit 2; } ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
  shift
done

echo "PORT=$PORT"
echo "SRC=$SRC"
echo "CLEAN=$CLEAN  DRY_RUN=$DRYRUN  VERBOSE=$VERBOSE"
[[ -n "$FORCE_PAT" ]] && echo "FORCE pattern: $FORCE_PAT"
[[ -n "$ONLY_PAT"  ]] && echo "ONLY  pattern: $ONLY_PAT"
echo

[[ -d "$SRC" ]] || { echo "Source not found: $SRC" >&2; exit 1; }

# ------------ Helpers ------------
# Portable realpath for macOS (follows symlinks)
realpath_py() { python3 - <<'PY' "$1"
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
}

hash_file() {
  local p="$1"
  if [[ -L "$p" ]]; then
    local tgt; tgt="$(realpath_py "$p")"
    # If target missing, hash the (broken) link path string to force attention
    if [[ -f "$tgt" ]]; then
      shasum -a 1 "$tgt" | awk '{print $1}'
    else
      printf '%s' "$tgt" | shasum -a 1 | awk '{print $1}'
    fi
  else
    shasum -a 1 "$p" | awk '{print $1}'
  fi
}

size_file() {
  local p="$1"
  if [[ -L "$p" ]]; then
    local tgt; tgt="$(realpath_py "$p")"
    if [[ -f "$tgt" ]]; then stat -f %z "$tgt"; else echo 0; fi
  else
    stat -f %z "$p"
  fi
}

link_target() {
  local p="$1"
  if [[ -L "$p" ]]; then realpath_py "$p"; else echo "-"; fi
}

# Creates parent dirs on the device without touching IFS or using exist_ok
ensure_remote_dir() {
  local rel="$1"
  local dir="${rel%/*}"
  [[ "$dir" == "$rel" ]] && return 0  # file lives at root

  local path=""
  # zsh split on '/' using parameter expansion, avoids IFS
  local -a parts; parts=("${(s:/:)dir}")
  local part
  for part in "${parts[@]}"; do
    [[ -z "$part" ]] && continue
    path="$path/$part"
    # mkdir each level; ignore "already exists"
    mpremote connect "$PORT" fs mkdir ":$path" >/dev/null 2>&1 || true
  done
}

matches_only() {
  local rel="$1"
  [[ -z "$ONLY_PAT" ]] && return 0
  [[ "$rel" == ${~ONLY_PAT} ]] && return 0 || return 1
}

matches_force() {
  local rel="$1"
  [[ -z "$FORCE_PAT" ]] && return 1
  [[ "$rel" == ${~FORCE_PAT} ]]
}

# ------------ Scan local ------------
echo "Scanning local files..."
cd "$SRC"

# Build current manifest (hash size relpath linktarget)
tmp_manifest="$(mktemp)"
IFS=$'\n'
# Follow symlinks to dirs (-L), include regular files and symlinks
for f in $(find -L . \( -type f -o -type l \) \
  -not -path '*/.git/*' \
  -not -path '*/__pycache__/*' \
  -not -name '.*.swp' \
  -not -name '*.pyc' \
  -not -name '.DS_Store' \
); do
  rel="${f#./}"
  matches_only "$rel" || continue
  h="$(hash_file "$rel")"
  s="$(size_file "$rel")"
  lt="$(link_target "$rel")"
  [[ "$VERBOSE" == yes ]] && [[ -L "$rel" ]] && echo "  symlink: $rel -> $lt"
  print -r -- "$h $s $rel $lt" >> "$tmp_manifest"
done
unset IFS
sort -k3 "$tmp_manifest" -o "$tmp_manifest"

# Load previous manifest
typeset -A prev_hash prev_size prev_lt
if [[ -f "$MANIFEST" ]]; then
  while IFS=$' ' read -r h s p lt_rest; do
    prev_hash[$p]="$h"
    prev_size[$p]="$s"
    # join rest of fields as target (handles spaces, though we avoid them)
    prev_lt[$p]="${lt_rest:-"-"}"
  done < "$MANIFEST"
fi

# Decide changes
typeset -a to_upload to_delete
while IFS=$' ' read -r h s p lt; do
  if matches_force "$p"; then
    to_upload+=("$p"); continue
  fi
  if [[ ! -v "prev_hash[$p]" ]]; then
    to_upload+=("$p"); continue
  fi
  # Upload if content hash changed OR symlink target path changed
  if [[ "$h" != "${prev_hash[$p]}" || "$lt" != "${prev_lt[$p]:--}" ]]; then
    to_upload+=("$p")
  fi
done < "$tmp_manifest"

if [[ "$CLEAN" == "yes" && -f "$MANIFEST" ]]; then
  typeset -A now_present; now_present=()
  while IFS=$' ' read -r _ _ p _; do now_present[$p]=1; done < "$tmp_manifest"
  while IFS=$' ' read -r _ _ p _; do
    if [[ -z "${now_present[$p]:-}" ]]; then
      # Respect --only: only delete inside the restricted subtree
      matches_only "$p" || continue
      to_delete+=("$p")
    fi
  done < "$MANIFEST"
fi

echo "Planned changes:"
echo "  Upload: ${#to_upload} file(s)"
[[ "$CLEAN" == "yes" ]] && echo "  Delete: ${#to_delete:-0} file(s)"
[[ "$DRYRUN" == "yes" ]] && echo "(dry-run; no changes will be made)"
echo

# ------------ Execute ------------
if (( ${#to_upload} > 0 )); then
  for rel in "${to_upload[@]}"; do
    echo "UP  $rel"
    if [[ "$DRYRUN" == "no" ]]; then
      ensure_remote_dir "$rel"
      mpremote connect "$PORT" fs cp "$SRC/$rel" "$DEST_PREFIX$rel"
    fi
  done
fi

if [[ "$CLEAN" == "yes" && ${#to_delete:-0} -gt 0 ]]; then
  for rel in "${to_delete[@]}"; do
    echo "RM  $rel"
    if [[ "$DRYRUN" == "no" ]]; then
      mpremote connect "$PORT" fs rm "$DEST_PREFIX$rel" || true
    fi
  done
fi

# ------------ Extra device-side shallow clean using `mpremote fs ls` ------------
# Deletes remote-only files under each top-level local project directory (e.g., logos, lib).
# Does not recurse; ideal for flat asset dirs. Honors --only.
if [[ "$CLEAN" == "yes" ]]; then
  echo
  echo "Clean pass (fs ls): removing remote files not present locally (shallow, per project dir)."

  # Build current local file set and collect unique top-level directories that actually exist locally.
  typeset -A present_now; present_now=()
  typeset -A roots; roots=()
  while IFS=$' ' read -r _ _ p _; do
    [[ -z "$p" ]] && continue
    present_now[$p]=1
    # Capture top-level dir if path contains a slash
    if [[ "$p" == */* ]]; then
      top="${p%%/*}"
      [[ -d "$SRC/$top" ]] && roots[$top]=1
    fi
  done < "$tmp_manifest"

  # For each local top-level dir, list remote shallow entries with `fs ls` and delete remote-only files
  for root in "${(@k)roots}"; do
    # Only shallow-clean directories we expect to be flat asset folders.
    # If you want to limit to specific dirs (e.g., logos), uncomment the filter:
    # [[ "$root" != "logos" && "$root" != "lib" ]] && continue

    remote_dir=":/$root"
    tmp_ls="$(mktemp)"
    if ! mpremote connect "$PORT" fs ls "$remote_dir" > "$tmp_ls" 2>/dev/null; then
      # Try without the leading slash (some ports accept :dir)
      remote_dir=":$root"
      if ! mpremote connect "$PORT" fs ls "$remote_dir" > "$tmp_ls" 2>/dev/null; then
        [[ "$VERBOSE" == "yes" ]] && echo "Skip: cannot ls $remote_dir"
        rm -f "$tmp_ls"
        continue
      fi
    fi

    # Parse names from ls output: last whitespace-separated field; trim trailing '/'
    tmp_remote_files="$(mktemp)"
    awk 'NF{n=$NF; gsub(/\/$/,"",n); if(n!="." && n!=".."){print n}}' "$tmp_ls" | sort > "$tmp_remote_files"

    # Build local shallow file list for this root
    tmp_local_files="$(mktemp)"
    if [[ -d "$SRC/$root" ]]; then
      ( cd "$SRC/$root" && find . -maxdepth 1 -type f -print | sed 's|^\./||' | sort ) > "$tmp_local_files"
    else
      : > "$tmp_local_files"
    fi

    # Compute remote-only (present remotely but not locally)
    tmp_to_delete="$(mktemp)"
    comm -23 "$tmp_remote_files" "$tmp_local_files" > "$tmp_to_delete"

    if [[ -s "$tmp_to_delete" ]]; then
      echo "Remote-only files under /$root to delete:"
      cat "$tmp_to_delete"
      if [[ "$DRYRUN" == "no" ]]; then
        while IFS= read -r name; do
          [[ -z "$name" ]] && continue
          rel="$root/$name"
          # Respect --only filters
          matches_only "$rel" || continue
          echo "DEL $rel"
          mpremote connect "$PORT" fs rm "$DEST_PREFIX$rel" >/dev/null 2>&1 || true
        done < "$tmp_to_delete"
      else
        echo "(dry-run) Skipping deletions in /$root"
      fi
    else
      [[ "$VERBOSE" == "yes" ]] && echo "No remote-only files under /$root"
    fi

    rm -f "$tmp_ls" "$tmp_remote_files" "$tmp_local_files" "$tmp_to_delete"
  done
fi
# ------------ End extra clean ------------

# Save new manifest
if [[ "$DRYRUN" == "no" ]]; then
  cp "$tmp_manifest" "$MANIFEST"
  echo
  echo "Sync complete. Manifest updated: $MANIFEST"
else
  echo
  echo "Dry-run complete. No changes made."
fi

rm -f "$tmp_manifest"
