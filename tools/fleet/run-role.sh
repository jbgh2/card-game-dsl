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
#                skipped run is a recorded event, never a silent no-op;
#   delivery   — every run must land a report carrying this run's marker
#                in the fleet ledger, or the wrapper writes the failure /
#                no-report record itself with the log tail. A round
#                whose report lands nowhere a reader will see did not
#                finish its round. The fleet ledger is a file in this
#                clone, so delivery does not depend on the network.
# The whole body is one function invoked on the last line: the file is
# fully parsed before anything runs, so the in-run hard-sync may rewrite
# this script on disk without corrupting the executing copy (the update
# takes effect next run).
set -euo pipefail

main() {
  FLEET="/Users/benh/Projects/cardlang-fleet"
  CLAUDE_BIN="/Users/benh/.local/bin/claude"
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
  LEDGER="$LOGDIR/ledger.md"
  REPORTS_DIR="$LOGDIR/reports"
  mkdir -p "$LOGDIR" "$REPORTS_DIR"
  LOG="$LOGDIR/$ROLE-$STAMP.log"
  REPORT="$REPORTS_DIR/$RUN_ID.md"

  # The fleet ledger's entry format is a two-party contract:
  # tools/fleet/war-room.sh, section 6, is the reader, and parses an entry as
  # the `## <UTC timestamp> <run id>` header line plus the lines to the next
  # such header — so the timestamp is what tells a header from a `##` heading
  # inside a report body.
  #
  # Serialization is the micro-lock below, not O_APPEND: a skip entry is
  # appended by a run that does NOT hold the role lock, and a full report is
  # large enough that its append is several writes, so a skip header can land
  # inside a report body without one. mkdir is the atomic test-and-set; the
  # spin is bounded, because delivery must never deadlock — past the bound the
  # entry is appended anyway; and a lock dir old enough to be a crashed
  # appender's is reclaimed rather than left to wedge the ledger.
  #
  # post RETURNS the append's status. A caller that must not have its own exit
  # status masked says `|| true` at the call site; the one caller that acts on
  # the result — the consume path — branches on it, because deleting the only
  # copy of a report whose append failed is the loss this status exists to
  # prevent.
  post() { # post "$body" -> 0 iff the entry reached the fleet ledger
    local mlock="$LEDGER.lock" waited=0 held=0 rc=0
    while [ "$waited" -le 120 ]; do  # 120 * 0.25s = ~30s
      if mkdir "$mlock" 2>/dev/null; then held=1; break; fi
      if [ "$(( $(date +%s) - $(stat -f %m "$mlock" 2>/dev/null || date +%s) ))" -gt 120 ]; then
        rm -rf "$mlock" 2>/dev/null || true
        continue
      fi
      waited=$((waited + 1))
      sleep 0.25
    done
    printf '## %s %s\n%s\n\n' "$(date -u +%FT%TZ)" "$RUN_ID" "$1" >> "$LEDGER"
    rc=$?
    if [ "$held" -eq 1 ]; then rm -rf "$mlock" 2>/dev/null || true; fi
    return "$rc"
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
      post "**$ROLE run skipped** at $(date -u +%FT%TZ): fleet clone busy ($HOLDER)." || true
      exit 0
    fi
    rm -rf "$LOCK"
    if ! mkdir "$LOCK" 2>/dev/null; then
      post "**$ROLE run skipped** at $(date -u +%FT%TZ): lost the lock race while reclaiming (was: $HOLDER)." || true
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

Run marker: this run is $RUN_ID. Write your report to the file $REPORT — it MUST contain the literal line $MARKER — and the wrapper verifies delivery by that file and appends it to the fleet ledger." >"$LOG" 2>&1 &
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
$(tail_block)" || true
    exit "$STATUS"
  fi

  # Delivery: only a report file carrying this run's marker counts — a file
  # left by an earlier run, or a stub the round never filled in, would
  # otherwise mask a missing report. The report is consumed on delivery: the
  # fleet ledger is the record, and a second copy beside it would drift — but
  # only once the append has actually landed, so a read-only ledger or a full
  # disk costs the round its page entry and not the report itself. A file that
  # fails the check is LEFT where it is, for forensics.
  if [ -f "$REPORT" ] && grep -qF "$MARKER" "$REPORT"; then
    if post "$(cat "$REPORT")"; then
      rm -f "$REPORT"
    fi
  else
    post "**$ROLE run ended with no report** (exit 0, marker $RUN_ID absent from \`$REPORT\`), started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)" || true
  fi

  # Keep the last 30 role logs.
  ls -1t "$LOGDIR" | grep -E "^(warden|dispatcher)-" | tail -n +31 | while read -r f; do rm -f "$LOGDIR/$f"; done
  # Keep the last 30 undelivered report files.
  ls -1t "$REPORTS_DIR" | tail -n +31 | while read -r f; do rm -f "$REPORTS_DIR/$f"; done
}

main "$@"
exit $?
