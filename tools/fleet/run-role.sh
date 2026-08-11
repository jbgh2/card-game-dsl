#!/bin/bash
# Runs one Standing Role headless in the fleet clone (docs/harness.md,
# "Standing Roles"; issue #317). The engine is `claude -p` under the
# permission charter (.claude/settings.json) — liturgies run, everything
# else is denied loudly. The wrapper owns what the engine cannot
# guarantee about itself:
#   freshness  — the clone is hard-synced to origin/main before the run;
#   occupancy  — one role in the clone at a time, and a skipped run is a
#                public event, never a silent no-op;
#   delivery   — a run that ends without its report on the fleet epic
#                gets a wrapper-posted record with the log tail. A round
#                whose report lands nowhere a reader will see did not
#                finish its round.
# Invoke via the launchd stub (tools/fleet/launchd/) or after freshening
# the clone by hand — the stub re-reads this file only after sync, so a
# mid-run self-update cannot corrupt the running script.
set -euo pipefail

FLEET="/Users/benh/Projects/cardlang-fleet"
CLAUDE_BIN="/Users/benh/.local/bin/claude"
REPO="jbgh2/card-game-dsl"
REPORT_ISSUE=274
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROLE="${1:-}"
case "$ROLE" in
  warden)     TIMEOUT_S=3600 ;;
  dispatcher) TIMEOUT_S=14400 ;;
  *) echo "usage: run-role.sh warden|dispatcher" >&2; exit 64 ;;
esac

STAMP="$(date +%Y%m%d-%H%M%S)"
LOGDIR="$FLEET/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/$ROLE-$STAMP.log"

post() { # post "$body" — best-effort; delivery failure must not mask run status
  gh issue comment "$REPORT_ISSUE" --repo "$REPO" --body "$1" || true
}

tail_block() { printf '```\n%s\n```' "$(tail -c 1500 "$LOG" 2>/dev/null || echo "(no log)")"; }

# Single occupancy: mkdir is the atomic test-and-set.
LOCK="$FLEET/.role-lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  HOLDER="$(cat "$LOCK/holder" 2>/dev/null || echo unknown)"
  post "**$ROLE run skipped** at $(date -u +%FT%TZ): fleet clone busy ($HOLDER)."
  exit 0
fi
echo "$ROLE since $(date -u +%FT%TZ)" > "$LOCK/holder"
trap 'rm -rf "$LOCK"' EXIT

cd "$FLEET"
git fetch -q origin
git checkout -qB main origin/main
git worktree prune 2>/dev/null || true

RUN_START="$(date -u +%FT%TZ)"

# Wall-clock watchdog: a hung engine becomes a failed run with a log,
# never a stuck launchd job.
set +e
"$CLAUDE_BIN" -p --permission-mode default \
  "$(cat "$FLEET/tools/fleet/prompts/$ROLE.md")" >"$LOG" 2>&1 &
ENGINE=$!
( sleep "$TIMEOUT_S" && kill "$ENGINE" 2>/dev/null ) &
WATCHDOG=$!
wait "$ENGINE"
STATUS=$?
kill "$WATCHDOG" 2>/dev/null
wait "$WATCHDOG" 2>/dev/null
set -e

if [ "$STATUS" -ne 0 ]; then
  post "**$ROLE run FAILED** (exit $STATUS; 143 = watchdog kill at ${TIMEOUT_S}s), started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)"
  exit "$STATUS"
fi

# Delivery check: any comment on the report issue newer than RUN_START
# counts as the report having landed.
NEW="$(gh api "repos/$REPO/issues/$REPORT_ISSUE/comments?since=$RUN_START&per_page=100" --jq 'length' 2>/dev/null || echo unverifiable)"
if [ "$NEW" = "unverifiable" ]; then
  post "**$ROLE run ended (exit 0) but delivery is unverifiable** (comment query failed), started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)"
elif [ "$NEW" -eq 0 ]; then
  post "**$ROLE run ended with no report** (exit 0), started $RUN_START, log \`$LOG\`. Tail:
$(tail_block)"
fi

# Keep the last 30 role logs.
ls -1t "$LOGDIR" | grep -E "^(warden|dispatcher)-" | tail -n +31 | while read -r f; do rm -f "$LOGDIR/$f"; done
