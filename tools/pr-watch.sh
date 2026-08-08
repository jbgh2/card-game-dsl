#!/usr/bin/env bash
# tools/pr-watch.sh — the author's alarm clock on an open PR.
#
# docs/harness.md ("Review threads") owns the rule: the session that opens
# a PR arms this watcher and handles its own review rounds in-context.
# This file is the alarm, never the handler. It watches two INDEPENDENT
# signals concurrently — review activity (new reviews or review comments
# since arming) and the gate (every check completed, pass or fail) — and
# exits 0 with a reason line on whichever fires first. Always run it in
# the background: it sleeps.
#
# Usage: pr-watch.sh <pr> [mode] [interval-s] [timeout-s]
#   mode: "both" (default) — exit on review activity OR gate completion
#         "reviews" — exit on review activity only (re-arm form, for when
#         the gate already completed on a previous wake)
# Exit: 0 = signal fired (reason on stdout); 3 = timeout.
set -euo pipefail

REPO=jbgh2/card-game-dsl
N=${1:?usage: pr-watch.sh <pr> [both|reviews] [interval] [timeout]}
MODE=${2:-both}
INT=${3:-60}
TO=${4:-2700}

count() { gh api --paginate "repos/$REPO/pulls/$N/$1" --jq length | awk '{ s += $1 } END { print s + 0 }'; }

base_c=$(count comments)
base_r=$(count reviews)
start=$(date +%s)

while :; do
  now=$(date +%s)
  if [ $((now - start)) -ge "$TO" ]; then
    echo "pr-watch: TIMEOUT after ${TO}s on PR #$N (no review activity$([ "$MODE" = both ] && echo ", gate still running"))"
    exit 3
  fi
  c=$(count comments); r=$(count reviews)
  if [ "$c" -gt "$base_c" ] || [ "$r" -gt "$base_r" ]; then
    echo "pr-watch: review activity on PR #$N (comments $base_c -> $c, reviews $base_r -> $r)"
    exit 0
  fi
  if [ "$MODE" = both ]; then
    counts=$(gh pr view "$N" --repo "$REPO" --json statusCheckRollup --jq \
      '"\(.statusCheckRollup | length) \([.statusCheckRollup[] | select(.__typename == "CheckRun" and .status != "COMPLETED")] | length)"')
    total=${counts% *}; pending=${counts#* }
    # An empty rollup is a freshly-pushed head whose runs have not registered
    # yet, never a completed gate — the sibling of merge-gate.sh's "no checks
    # reported" refusal (that Owner Guard's class, applied to the watcher):
    # zero-total waits, it does not fire.
    if [ "$total" -ge 1 ] && [ "$pending" -eq 0 ]; then
      echo "pr-watch: every check completed on PR #$N ($total runs)"
      exit 0
    fi
  fi
  sleep "$INT"
done
