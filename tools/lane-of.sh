#!/usr/bin/env bash
# tools/lane-of.sh — mechanical Merge Lane classification of a diff.
#
# docs/harness.md ("The Merge Lanes") owns the table; this reads its Paths
# column — docs-as-data — and takes, per file, the supremum lane (earliest
# letter) across every row the file matches, then the supremum across
# files. Twin rows sharing a path resolve to their stricter twin; relaxing
# to the softer twin is judgment this script never performs. A file
# matching no row is reported unmapped and defaults to Merge Lane B (the
# table's missing-class rule).
#
# Usage: lane-of.sh --range BASE..HEAD   |   lane-of.sh FILE...
# Output: one line per file (lane, matched classes or "unmapped->B"),
# then "lane: X" and "agent-mergeable: yes|no" (yes iff X is C or D).
set -euo pipefail

HARNESS="$(cd "$(dirname "$0")/.." && pwd)/docs/harness.md"

files=()
if [ "${1:-}" = "--range" ]; then
  [ $# -eq 2 ] || { echo "usage: lane-of.sh --range BASE..HEAD | lane-of.sh FILE..." >&2; exit 2; }
  while IFS= read -r f; do files+=("$f"); done < <(git diff --name-only "$2")
else
  [ $# -ge 1 ] || { echo "usage: lane-of.sh --range BASE..HEAD | lane-of.sh FILE..." >&2; exit 2; }
  files=("$@")
fi
[ "${#files[@]}" -ge 1 ] || { echo "empty diff — nothing to classify" >&2; exit 2; }

# Parse the lane table: emit "LANE<TAB>GLOB<TAB>CLASS" per glob.
rows=$(awk -F'|' '
  /^\| Change class \| Paths \| Merge Lane \|/ { t = 1; next }
  t && /^\|[- ]+\|/ { next }
  t && /^\|/ {
    cls = $2; paths = $3; lane = $4
    gsub(/`/, "", cls); gsub(/^ +| +$/, "", cls); gsub(/^ +| +$/, "", lane)
    if (paths ~ /—/) next
    n = split(paths, g, ",")
    for (i = 1; i <= n; i++) {
      gsub(/[ `]/, "", g[i])
      if (g[i] != "") printf "%s\t%s\t%s\n", lane, g[i], cls
    }
    next
  }
  t && !/^\|/ { t = 0 }
' "$HARNESS")
[ -n "$rows" ] || { echo "no Paths rows parsed from $HARNESS — table moved?" >&2; exit 2; }

glob_to_re() {
  # ** crosses /, * does not; dots are literal.
  printf '%s' "$1" | sed -e 's/[.]/\\./g' -e 's/\*\*/\x01/g' -e 's/\*/[^\/]*/g' -e 's/\x01/.*/g'
}

rank() { case "$1" in A) echo 1 ;; B) echo 2 ;; C) echo 3 ;; D) echo 4 ;; *) echo 2 ;; esac; }
letter() { case "$1" in 1) echo A ;; 2) echo B ;; 3) echo C ;; 4) echo D ;; esac; }

overall=4
for f in "${files[@]}"; do
  file_rank=99; matched=""
  while IFS=$'\t' read -r lane glob cls; do
    re="^$(glob_to_re "$glob")$"
    if printf '%s' "$f" | grep -qE "$re"; then
      r=$(rank "$lane")
      [ "$r" -lt "$file_rank" ] && file_rank=$r
      matched="${matched:+$matched; }$cls -> $lane"
    fi
  done <<<"$rows"
  if [ "$file_rank" -eq 99 ]; then
    file_rank=2; matched="unmapped->B (missing-class rule)"
  fi
  printf '%s\t%s\t%s\n' "$(letter $file_rank)" "$f" "$matched"
  [ "$file_rank" -lt "$overall" ] && overall=$file_rank
done

final=$(letter $overall)
echo "lane: $final"
if [ "$final" = C ] || [ "$final" = D ]; then echo "agent-mergeable: yes"; else echo "agent-mergeable: no"; fi
