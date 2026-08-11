#!/bin/bash
# Runs one Standing Role headless in the fleet clone (docs/harness.md,
# "Standing Roles"; issue #317). The engine is `claude -p` under the
# permission charter (.claude/settings.json) — liturgies run, everything
# else is denied loudly. The wrapper owns what the engine cannot
# guarantee about itself:
#   freshness  — the clone is hard-synced (fetch + reset --hard) to
#                origin/main before the run, under the lock;
#   occupancy  — one role in the clone at a time; a stale lock left by a
#                dead or overheld run is reclaimed, and a genuinely
#                skipped run is a public event, never a silent no-op;
#   delivery   — every run must land a report carrying this run's marker
#                on the fleet epic, or the wrapper posts the failure /
#                no-report record itself with the log tail. A round
#                whose report lands nowhere a reader will see did not
#                finish its round.
# The whole body is one function invoked on the last line: the file is
# fully parsed before anything runs, so the in-run hard-sync may rewrite
# this script on disk without corrupting the executing copy (the update
# takes effect next run).
set -euo pipefail

main() {
  FLEET="/Users/benh/Projects/cardlang-fleet"
  CLAUDE_BIN="/Users/benh/.local/bin/claude"
  REPO="jbgh2/card-game-dsl"
  REPORT_ISSUE=274
  MAX_HOLD_S=18000  # > the longest watchdog below; an older holder is wedged
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

  ROLE="${1:-}"
  case "$ROLE" in
    warden)     TIMEOUT_S=3600 ;;
    dispatcher) TIMEOUT_S=14400 ;;
    *) echo "usage: run-role.sh warden|dispatcher" >&2; exit 64 ;;
  esac

  STAMP="$(date +%Y%m%d-%H%M%S)"
  RUN_ID="$ROLE-$STAMP-$$"
  MARKER="<!-- fleet-run:$RUN_ID -->"
  LOGDIR="$FLEET/logs"
  mkdir -p "$LOGDIR"
  LOG="$LOGDIR/$ROLE-$STAMP.log"

  post() { # post "$body" — best-effort; delivery failure must not mask run status
    gh issue comment "$REPORT_ISSUE" --repo "$REPO" --body "$1" || true
  }

  tail_block() { printf '```\n%s\n```' "$(tail -c 1500 "$LOG" 2>/dev/null || echo "(no log)")"; }

  # Occupancy: mkdir is the atomic test-and-set. On contention, reclaim
  # iff the recorded holder is dead or has held past MAX_HOLD_S — a
  # power cut must not disable the fleet until a human notices.
  LOCK="$FLEET/.role-lock"
  if ! mkdir "$LOCK" 2>/dev/null; then
    HOLDER="$(cat "$LOCK/holder" 2>/dev/null || echo "unknown pid=0")"
    HOLDER_PID="$(printf '%s' "$HOLDER" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p')"
    HOLDER_AGE=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || date +%s) ))
    if [ -n "$HOLDER_PID" ] && kill -0 "$HOLDER_PID" 2>/dev/null && [ "$HOLDER_AGE" -le "$MAX_HOLD_S" ]; then
      post "**$ROLE run skipped** at $(date -u +%FT%TZ): fleet clone busy ($HOLDER)."
      exit 0
    fi
    rm -rf "$LOCK"
    if ! mkdir "$LOCK" 2>/dev/null; then
      post "**$ROLE run skipped** at $(date -u +%FT%TZ): lost the lock race while reclaiming (was: $HOLDER)."
      exit 0
    fi
    echo "reclaimed stale lock (was: $HOLDER, age ${HOLDER_AGE}s)" >&2
  fi
  echo "$ROLE pid=$$ since $(date -u +%FT%TZ)" > "$LOCK/holder"
  # Cleanup owns the wall refresh (issue #279): it must run on EVERY exit
  # path — engine failure and watchdog kill included — and only after the
  # lock is released, or the page records a finished role as RUN IN
  # FLIGHT. Best-effort, never a gate on the round.
  cleanup() {
    rm -rf "$LOCK"
    "$FLEET/tools/fleet/war-room.sh" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT

  # Freshness, under the lock: reset --hard is the sync — checkout -B
  # alone re-points the ref but carries dirty tracked edits into the
  # run, and a dirty prompt or wrapper must not survive to execute.
  cd "$FLEET"
  git fetch -q origin
  git checkout -qB main origin/main
  git reset -q --hard origin/main
  git worktree prune 2>/dev/null || true

  RUN_START="$(date -u +%FT%TZ)"

  # Wall-clock watchdog: a hung engine becomes a failed run with a log,
  # never a stuck launchd job.
  set +e
  "$CLAUDE_BIN" -p --permission-mode default \
    "$(cat "$FLEET/tools/fleet/prompts/$ROLE.md")

Run marker: this run is $RUN_ID. The report comment you post on epic #$REPORT_ISSUE MUST contain the literal line $MARKER — the wrapper verifies delivery by that marker." >"$LOG" 2>&1 &
  ENGINE=$!
  ( sleep "$TIMEOUT_S" && kill "$ENGINE" 2>/dev/null ) &
  WATCHDOG=$!
  wait "$ENGINE"
  STATUS=$?
  kill "$WATCHDOG" 2>/dev/null
  wait "$WATCHDOG" 2>/dev/null
  set -e

  if [ "$STATUS" -ne 0 ]; then
    post "**$ROLE run FAILED** (exit $STATUS; 143 = watchdog kill at ${TIMEOUT_S}s), run $RUN_ID, started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)"
    exit "$STATUS"
  fi

  # Delivery: only a comment carrying this run's marker counts as the
  # report — any-comment-since would let unrelated traffic on the epic
  # mask a missing report.
  FOUND="$(gh api "repos/$REPO/issues/$REPORT_ISSUE/comments?since=$RUN_START&per_page=100" \
    --jq "[.[] | select(.body | contains(\"$MARKER\"))] | length" 2>/dev/null || echo unverifiable)"
  if [ "$FOUND" = "unverifiable" ]; then
    post "**$ROLE run ended (exit 0) but delivery is unverifiable** (comment query failed), run $RUN_ID, started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)"
  elif [ "$FOUND" -eq 0 ]; then
    post "**$ROLE run ended with no report** (exit 0, marker $RUN_ID absent from epic comments), started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)"
  fi

  # Keep the last 30 role logs.
  ls -1t "$LOGDIR" | grep -E "^(warden|dispatcher)-" | tail -n +31 | while read -r f; do rm -f "$LOGDIR/$f"; done
}

main "$@"
exit $?
