#!/bin/bash
# tools/fleet/war-room.sh -- "The war-room": generator for the operator's
# pull-based pulse page over the Standing Role fleet (docs/harness.md,
# "Standing Roles"; issue #279). Derives live fleet state -- role runs and the
# occupancy lock in the fleet clone, the running round's own progress, live
# Leases, open PRs, the Ready Front, the latest fleet reports on issue #274 --
# and writes ONE self-contained static HTML file (default
# /Users/benh/Projects/cardlang-fleet/war-room/index.html; -o PATH overrides).
# Failure discipline: a section whose derivation fails renders IN PLACE with a
# red FAILED banner and the error text (never silently empty, never dropped),
# the page is always written, and the script exits 1; exit 0 means every
# section derived.
# `--derive <name> ARG...` prints one derived string and exits, without
# touching the page: the seam tests/test_war_room_progress.py drives, so the
# per-round progress line and the run-log line are provable against synthetic
# inputs rather than against whatever the fleet happens to be doing.

set -euo pipefail

# Byte-oriented text tools: BSD sed/awk/cut must never die on stray non-UTF-8
# bytes in log tails; escaping below is single-byte characters only, so this
# changes nothing about its correctness.
export LC_ALL=C

REPO="jbgh2/card-game-dsl"
FLEET_CLONE="/Users/benh/Projects/cardlang-fleet"
LOGS_DIR="$FLEET_CLONE/logs"
LOCK_HOLDER="$FLEET_CLONE/.role-lock/holder"
REPORTS_ISSUE="274"
READY_FRONT_TIMEOUT=90

# Where the headless engine writes its transcript live: one directory per
# working copy under ~/.claude/projects, named by replacing every
# non-alphanumeric byte of the path with a dash. Derived from FLEET_CLONE
# rather than spelled out, so the two cannot drift if the clone moves.
# ${HOME:-} deliberately: an environment without HOME must cost the page one
# named "not derivable" line, not the whole build via set -u.
TRANSCRIPTS="${HOME:-}/.claude/projects/$(printf '%s' "$FLEET_CLONE" | sed 's/[^A-Za-z0-9]/-/g')"

# One line of progress must stay one line: a command with a heredoc in it is
# a page-wide wall of text otherwise. A run log's last line gets a far longer
# budget -- it is the only thing the Runs table says about a run.
PROGRESS_TEXT_LIMIT=200
LOG_LINE_LIMIT=400

# Resolve everything from the script's own location so the generator works
# from any cwd (and from the serve wrapper).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
READY_FRONT="$SCRIPT_DIR/../ready-front.sh"

USAGE="usage: war-room.sh [-o PATH] | war-room.sh --derive <progress-line HOLDER ROOT | last-log-line PATH>"
OUT="$FLEET_CLONE/war-room/index.html"
OUT_GIVEN=0
DERIVE=0
DERIVE_ARGV=()
while [ $# -gt 0 ]; do
  case "$1" in
    -o)
      [ $# -ge 2 ] || { echo "war-room.sh: -o requires a path" >&2; exit 2; }
      OUT="$2"
      OUT_GIVEN=1
      shift 2
      ;;
    --derive)
      [ $# -ge 2 ] || { echo "war-room.sh: --derive requires a derivation name ($USAGE)" >&2; exit 2; }
      DERIVE=1
      shift
      DERIVE_ARGV=("$@")
      break
      ;;
    -h|--help)
      echo "$USAGE" >&2
      exit 0
      ;;
    *)
      echo "war-room.sh: unknown argument: $1 ($USAGE)" >&2
      exit 2
      ;;
  esac
done

# The single escape helper. EVERY piece of derived text (log lines, PR titles,
# report bodies, ready-front output, error text) passes through here before it
# is inserted into HTML: none of it is trusted markup. Order matters: & first,
# then < then > then the double quote, so entities are not double-escaped.
html_escape() {
  sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'
}

esc() { printf '%s' "$1" | html_escape; }

# ------------------------------------------------------- derived: what a round
# is doing. `RUN IN FLIGHT` says the door is shut; on its own it says nothing
# about the round, whose log stays empty until it ends. The engine writes its
# transcript live, so the progress is derivable -- and because a derived line
# reads as authoritative, every way this can fail to name the round's work
# names ITSELF instead. There is no blank outcome and no guess.

# $1 = the fixed reason (kept literal: tests/test_war_room_progress.py scrapes
# this call's first argument to pin the reason vocabulary), $2 = free detail.
not_derivable() {
  if [ -n "${2:-}" ]; then
    printf 'progress: not derivable (%s: %s)' "$1" "$2"
  else
    printf 'progress: not derivable (%s)' "$1"
  fi
}

# progress_line HOLDER-FILE TRANSCRIPT-ROOT -- one line, always, exit 0 always.
progress_line() {
  local holder="$1" root="$2"
  local since_raw since_epoch listing newest newest_mtime newest_path
  local raw jq_rc steps work clock

  [ -r "$holder" ] || { not_derivable "lock holder unreadable" "$holder"; return 0; }
  # `;q` rather than `| head -1`: run-role.sh writes the record on line one,
  # and the pipe would carry the same SIGPIPE-under-pipefail hazard avoided
  # below.
  since_raw="$(sed -n 's/.*[[:space:]]since[[:space:]]\([^[:space:]][^[:space:]]*\).*/\1/p;q' "$holder" 2>/dev/null)" || since_raw=""
  since_epoch="$(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$since_raw" '+%s' 2>/dev/null)" || since_epoch=""
  [ -n "$since_epoch" ] || { not_derivable "lock holder carries no start time" "$holder"; return 0; }

  [ -d "$root" ] || { not_derivable "no transcript directory" "$root"; return 0; }
  listing="$(find "$root" -maxdepth 1 -name '*.jsonl' -exec stat -f '%m|%N' {} + 2>/dev/null)" || listing=""
  [ -n "$listing" ] || { not_derivable "no transcript files" "$root"; return 0; }
  # awk, not `sort -rn | head -1`: head closing the pipe early can leave sort
  # killed by SIGPIPE, which pipefail would report as a failed derivation.
  # Only numeric mtimes: the comparison below is arithmetic, and a `[ x -ge n ]`
  # on a malformed listing would kill the whole page build under set -e -- the
  # one thing this generator promises never to do.
  newest="$(printf '%s\n' "$listing" | awk -F'|' '$1 ~ /^[0-9]+$/ && $1 + 0 >= m { m = $1 + 0; line = $0 } END { print line }')"
  [ -n "$newest" ] || { not_derivable "no transcript files" "$root"; return 0; }
  newest_mtime="${newest%%|*}"
  newest_path="${newest#*|}"

  # The round's transcript is necessarily written after the lock was taken.
  # An older newest file means the newest session belongs to somebody else --
  # the operator working in the clone -- and showing it would be a confident
  # wrong answer, which is worse than the silence this replaces.
  [ "$newest_mtime" -ge "$since_epoch" ] || { not_derivable "newest transcript predates the lock" "$newest_path"; return 0; }

  # "A" per assistant step, "T<work>" per tool call within it. The transcript
  # is appended to WHILE this reads it, so a truncated final line is normal
  # traffic, not a failure: jq exits nonzero having already emitted every
  # record it did parse, and that prefix is what the line is built from.
  jq_rc=0
  raw="$(jq -r '
    select(.type == "assistant")
    | ( "A",
        ( .message.content[]? | select(.type == "tool_use")
          | "T" + ( ( [ .input.description?, .input.command?, .input.file_path?, .name? ]
                      | map(select(type == "string" and . != "")) | .[0] // "(unnamed tool call)" )
                    | gsub("[[:space:]]+"; " ") ) ) )' "$newest_path" 2>/dev/null)" || jq_rc=$?
  if [ -z "$raw" ]; then
    if [ "$jq_rc" -ne 0 ]; then
      not_derivable "transcript unparsable" "$newest_path"
    else
      not_derivable "no assistant step yet" "$newest_path"
    fi
    return 0
  fi

  steps="$(printf '%s\n' "$raw" | awk '/^A$/ { n++ } END { print n + 0 }')"
  work="$(printf '%s\n' "$raw" | awk '/^T/ { last = substr($0, 2) } END { print last }')"
  [ -n "$work" ] || { not_derivable "no tool call yet" "$newest_path"; return 0; }
  if [ "${#work}" -gt "$PROGRESS_TEXT_LIMIT" ]; then
    work="$(printf '%s' "$work" | cut -c"1-$PROGRESS_TEXT_LIMIT") ..."
  fi
  clock="$(date -u -r "$newest_mtime" '+%H:%MZ' 2>/dev/null)" || clock="?"
  printf 'currently: %s (step %s, %s)' "$work" "$steps" "${clock:-?}"
}

# log_last_line PATH -- a run log's last non-empty line, bounded and, when it
# is bounded, SAYING so. A silently cut line reads as a complete statement:
# the witness is a benign startup warning cut mid-sentence into what looked
# like a denial (issue #366).
log_last_line() {
  local line
  line="$(awk 'NF { l = $0 } END { print l }' "$1" 2>&1)" || line="(unreadable)"
  if [ "${#line}" -gt "$LOG_LINE_LIMIT" ]; then
    line="$(printf '%s' "$line" | cut -c"1-$LOG_LINE_LIMIT") ..."
  fi
  printf '%s' "$line"
}

# The page inserts these two, and only these two, so the seam below renders
# exactly what the page renders -- escaping included.
progress_line_html() { progress_line "$1" "$2" | html_escape; }
log_last_line_html() { log_last_line "$1" | html_escape; }

if [ "$DERIVE" -eq 1 ]; then
  # --derive prints one string and writes no page, so an -o alongside it would
  # be accepted and ignored. Refuse instead: the seam that exists to prove
  # totality does not get to carry the defect class it proves against.
  [ "$OUT_GIVEN" -eq 0 ] || { echo "war-room.sh: --derive writes no page, so -o has no meaning with it" >&2; exit 2; }
  case "${DERIVE_ARGV[0]}" in
    progress-line)
      [ "${#DERIVE_ARGV[@]}" -eq 3 ] || { echo "war-room.sh: --derive progress-line requires HOLDER and ROOT" >&2; exit 2; }
      progress_line_html "${DERIVE_ARGV[1]}" "${DERIVE_ARGV[2]}"
      ;;
    last-log-line)
      [ "${#DERIVE_ARGV[@]}" -eq 2 ] || { echo "war-room.sh: --derive last-log-line requires PATH" >&2; exit 2; }
      log_last_line_html "${DERIVE_ARGV[1]}"
      ;;
    *)
      echo "war-room.sh: unknown derivation: ${DERIVE_ARGV[0]} ($USAGE)" >&2
      exit 2
      ;;
  esac
  echo
  exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/war-room.XXXXXX")"
OUT_TMP=""
cleanup() {
  rm -rf "$TMP" 2>/dev/null || true
  if [ -n "$OUT_TMP" ]; then rm -f "$OUT_TMP" 2>/dev/null || true; fi
}
trap cleanup EXIT

mkdir -p "$(dirname "$OUT")"
# Build next to the destination and mv at the end, so a reader never sees a
# half-written page.
OUT_TMP="${OUT}.tmp.$$"
: > "$OUT_TMP"

FAIL_COUNT=0
US=$'\x1f'

emit() { printf '%s\n' "$1" >> "$OUT_TMP"; }

# Failure discipline: render the failure in place, loudly, and remember it for
# the exit code. $1 = one-line reason, $2 = captured error text (may be empty).
emit_failed() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  emit "<div class=\"failed\">FAILED: $(esc "$1")</div>"
  if [ -n "${2:-}" ]; then
    emit "<pre class=\"err\">$(esc "$2")</pre>"
  fi
}

# A captured stream, labeled, escaped, in a pre block; empty is said out loud.
emit_pre_file() {
  emit "<div class=\"subhead\">$(esc "$1")</div>"
  if [ -s "$2" ]; then
    emit "<pre>$(html_escape < "$2")</pre>"
  else
    emit '<p class="muted">(empty)</p>'
  fi
}

# ------------------------------------------------------------------ page head
now_utc="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

cat >> "$OUT_TMP" <<'HEAD_HTML'
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The war-room</title>
<style>
:root { --bg:#f4f4f2; --panel:#ffffff; --fg:#16191c; --muted:#69717b;
        --line:#d8dbe0; --accent:#0b62d6; --fail:#b00020; --failfg:#ffffff;
        --hot:#7a5200; --hotbg:#ffe9b3; --prebg:#f0f1ee; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0f1113; --panel:#171a1d; --fg:#dfe2e6; --muted:#8b939d;
          --line:#2a2f35; --accent:#5da2ff; --fail:#d32f2f; --failfg:#ffffff;
          --hot:#ffd479; --hotbg:#3a2d0d; --prebg:#101316; }
}
body { margin:0; padding:12px 16px 40px; background:var(--bg); color:var(--fg);
       font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }
h1 { font-size:18px; margin:0 0 2px; }
h2 { font-size:11px; text-transform:uppercase; letter-spacing:.08em;
     color:var(--muted); margin:0 0 6px; }
.meta { color:var(--muted); font-size:12px; margin:0 0 12px; }
.sec { background:var(--panel); border:1px solid var(--line);
       padding:8px 10px; margin:0 0 10px; }
table { border-collapse:collapse; width:100%; font-size:12px; }
th { text-align:left; color:var(--muted); font-weight:600; }
th, td { padding:2px 10px 2px 0; border-bottom:1px solid var(--line);
         vertical-align:top; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
pre { background:var(--prebg); border:1px solid var(--line); padding:6px 8px;
      margin:4px 0; overflow-x:auto; white-space:pre-wrap; word-break:break-word;
      font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
        font-size:11px; }
.muted { color:var(--muted); }
.failed { background:var(--fail); color:var(--failfg); font-weight:700;
          padding:4px 8px; margin:4px 0; }
pre.err { border-color:var(--fail); }
.inflight { background:var(--hotbg); color:var(--hot); border:1px solid var(--hot);
            font-weight:700; padding:6px 8px; margin:0; white-space:pre-wrap; }
.progress { background:var(--hotbg); color:var(--hot); border:1px solid var(--hot);
            border-top:0; padding:4px 8px; margin:0 0 8px; white-space:pre-wrap;
            word-break:break-word;
            font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }
.subhead { color:var(--muted); font-size:11px; margin:6px 0 2px; }
.report { margin:0 0 10px; }
</style>
</head>
<body>
HEAD_HTML

# --------------------------------------------------------- section 1: header
emit '<h1>The war-room</h1>'
# Deliberate set +e island: a failed ls-remote must render FAILED in place,
# never kill the page build.
set +e
main_raw="$(git -C "$REPO_ROOT" ls-remote origin main 2>&1)"
main_rc=$?
set -e
main_sha=""
if [ "$main_rc" -eq 0 ] && [ -n "$main_raw" ]; then
  main_sha="$(printf '%s\n' "$main_raw" | awk 'NR == 1 { print substr($1, 1, 7) }')"
fi
if [ -n "$main_sha" ]; then
  emit "<div class=\"meta\">repo $(esc "$REPO") &middot; generated $(esc "$now_utc") &middot; main @ <span class=\"mono\">$(esc "$main_sha")</span> &middot; auto-refresh 60s</div>"
else
  emit "<div class=\"meta\">repo $(esc "$REPO") &middot; generated $(esc "$now_utc") &middot; auto-refresh 60s</div>"
  if [ "$main_rc" -eq 0 ]; then
    emit_failed "main tip: git ls-remote origin main returned nothing" "$main_raw"
  else
    emit_failed "main tip: git ls-remote origin main failed (exit $main_rc)" "$main_raw"
  fi
fi

# ----------------------------------------------------------- section 2: Runs
emit '<div class="sec" id="runs">'
emit '<h2>Runs</h2>'
if [ -e "$LOCK_HOLDER" ]; then
  # Deliberate set +e island: an unreadable holder file still renders, loudly,
  # with cat's error text standing in for the contents.
  set +e
  lock_holder_text="$(cat "$LOCK_HOLDER" 2>&1)"
  set -e
  emit "<div class=\"inflight\">RUN IN FLIGHT: $(esc "$lock_holder_text")</div>"
  emit "<div class=\"progress\">$(progress_line_html "$LOCK_HOLDER" "$TRANSCRIPTS")</div>"
fi
if [ ! -d "$LOGS_DIR" ]; then
  emit_failed "logs directory missing: $LOGS_DIR" ""
else
  # Deliberate set +e island: an unlistable logs directory renders FAILED,
  # never an empty table.
  set +e
  find "$LOGS_DIR" -maxdepth 1 \
    \( -name 'warden-*.log' -o -name 'dispatcher-*.log' \
       -o -name 'launchd-*.out' -o -name 'launchd-*.err' \) \
    -exec stat -f '%m|%z|%N' {} + 2> "$TMP/runs.err" | sort -rn > "$TMP/runs.all"
  runs_rc=$?
  set -e
  if [ "$runs_rc" -ne 0 ]; then
    emit_failed "listing run logs under $LOGS_DIR failed (exit $runs_rc)" "$(cat "$TMP/runs.err" 2>/dev/null)"
  elif [ ! -s "$TMP/runs.all" ]; then
    emit '<p class="muted">no run logs found (warden-*.log, dispatcher-*.log, launchd-*.out/err)</p>'
  else
    head -15 "$TMP/runs.all" > "$TMP/runs.top"
    runs_total="$(wc -l < "$TMP/runs.all" | tr -d ' ')"
    emit '<table>'
    emit '<tr><th>log</th><th>mtime (UTC)</th><th>bytes</th><th>last line</th></tr>'
    while IFS='|' read -r r_mtime r_size r_path; do
      [ -n "$r_path" ] || continue
      r_when="$(date -u -r "$r_mtime" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo '?')"
      emit "<tr><td>$(esc "$(basename "$r_path")")</td><td>$(esc "$r_when")</td><td>$(esc "$r_size")</td><td class=\"mono\">$(log_last_line_html "$r_path")</td></tr>"
    done < "$TMP/runs.top"
    emit '</table>'
    if [ "$runs_total" -gt 15 ]; then
      emit "<p class=\"muted\">showing newest 15 of $runs_total logs</p>"
    fi
  fi
fi
emit '</div>'

# ---------------------------------------------------- section 3: Live Leases
emit '<div class="sec" id="leases">'
emit '<h2>Live Leases</h2>'
# Deliberate set +e island: a failed ls-remote renders FAILED; an empty result
# is a legitimate "none".
set +e
git -C "$REPO_ROOT" ls-remote origin "refs/heads/claude/issue-*" > "$TMP/leases.raw" 2> "$TMP/leases.err"
leases_rc=$?
set -e
# A Lease is exactly claude/issue-<N> (docs/harness.md, "Leases"); other
# claude/* branches are not Leases and must not show as occupied work.
grep -E $'refs/heads/claude/issue-[0-9]+$' "$TMP/leases.raw" > "$TMP/leases.lst" 2>/dev/null || true
if [ "$leases_rc" -ne 0 ]; then
  emit_failed "git ls-remote origin refs/heads/claude/issue-* failed (exit $leases_rc)" "$(cat "$TMP/leases.err" 2>/dev/null)"
elif [ ! -s "$TMP/leases.lst" ]; then
  emit '<p class="muted">none</p>'
else
  emit '<table>'
  emit '<tr><th>Lease branch</th><th>tip</th></tr>'
  while read -r l_sha l_ref; do
    [ -n "$l_ref" ] || continue
    emit "<tr><td>$(esc "${l_ref#refs/heads/}")</td><td class=\"mono\">$(esc "${l_sha:0:7}")</td></tr>"
  done < "$TMP/leases.lst"
  emit '</table>'
fi
emit '</div>'

# ------------------------------------------------------- section 4: Open PRs
emit '<div class="sec" id="prs">'
emit '<h2>Open PRs</h2>'
# Deliberate set +e island: gh or jq failing renders FAILED, never a dead
# build and never a silently empty table.
set +e
prs_json="$(gh pr list --repo "$REPO" --limit 200 --json number,title,headRefName,updatedAt,statusCheckRollup 2> "$TMP/prs.err")"
prs_rc=$?
set -e
if [ "$prs_rc" -ne 0 ]; then
  emit_failed "gh pr list --repo $REPO failed (exit $prs_rc)" "$(cat "$TMP/prs.err" 2>/dev/null)"
elif [ -z "$prs_json" ]; then
  emit_failed "gh pr list returned no output (expected a JSON array)" "$(cat "$TMP/prs.err" 2>/dev/null)"
else
  # Checks summary buckets from statusCheckRollup: SUCCESS counts as ok;
  # hard-stop conclusions count as fail; anything else (queued, in progress,
  # pending, neutral, skipped, unknown) counts as pending-ish.
  set +e
  printf '%s\n' "$prs_json" | jq -r '
    .[]
    | (.statusCheckRollup // []) as $roll
    | ( if ($roll | length) == 0 then "no checks yet"
        else
          ( [ $roll[]
              | (.conclusion // .state // "")
              | ascii_upcase
              | ( if . == "SUCCESS" then "s"
                  elif (. == "FAILURE" or . == "ERROR" or . == "TIMED_OUT"
                        or . == "CANCELLED" or . == "ACTION_REQUIRED"
                        or . == "STARTUP_FAILURE") then "f"
                  else "p" end )
            ] ) as $b
          | ([ $b[] | select(. == "s") ] | length | tostring) + " ok / "
            + ([ $b[] | select(. == "f") ] | length | tostring) + " fail / "
            + ([ $b[] | select(. == "p") ] | length | tostring) + " pending"
        end ) as $checks
    | [ (.number | tostring), .title, .headRefName, (.updatedAt // ""), $checks ]
    | join("\u001f")
  ' > "$TMP/prs.rows" 2> "$TMP/prs_jq.err"
  prs_jq_rc=$?
  set -e
  if [ "$prs_jq_rc" -ne 0 ]; then
    emit_failed "deriving PR rows failed (jq exit $prs_jq_rc)" "$(cat "$TMP/prs_jq.err" 2>/dev/null)"
  elif [ ! -s "$TMP/prs.rows" ]; then
    emit '<p class="muted">none</p>'
  else
    # A result that fills the explicit limit is a capped read, not the
    # domain (CLAUDE.md, "The tracker" — silent caps): say so, loudly,
    # and still render the partial view beneath.
    prs_count="$(wc -l < "$TMP/prs.rows" | tr -d ' ')"
    if [ "$prs_count" -ge 200 ]; then
      emit_failed "gh pr list filled its --limit 200 — a capped read, not the domain" ""
    fi
    emit '<table>'
    emit '<tr><th>PR</th><th>title</th><th>branch</th><th>updated</th><th>checks</th></tr>'
    while IFS="$US" read -r pr_num pr_title pr_branch pr_updated pr_checks; do
      [ -n "$pr_num" ] || continue
      emit "<tr><td><a href=\"https://github.com/$REPO/pull/$(esc "$pr_num")\">#$(esc "$pr_num")</a></td><td>$(esc "$pr_title")</td><td class=\"mono\">$(esc "$pr_branch")</td><td>$(esc "${pr_updated/T/ }")</td><td>$(esc "$pr_checks")</td></tr>"
    done < "$TMP/prs.rows"
    emit '</table>'
  fi
fi
emit '</div>'

# ---------------------------------------------------- section 5: Ready Front
emit '<div class="sec" id="ready-front">'
emit '<h2>Ready Front</h2>'
if [ ! -f "$READY_FRONT" ]; then
  emit_failed "ready-front.sh not found at $READY_FRONT" ""
else
  # Deliberate set +e island: the sweep may fail or hang; either renders
  # FAILED with whatever partial output was captured, never a dead build.
  # macOS has no GNU timeout, so: background the sweep, background a
  # sleep-then-kill watchdog, wait on the sweep, then kill the watchdog.
  # The watchdog drops a sentinel file only when its kill actually fired,
  # which is how a timeout is told apart from an ordinary failure; killing
  # the watchdog subshell before its kill line runs means no stray kill can
  # ever hit a recycled pid. The watchdog is detached from our stdio so no
  # background writer can hold a caller's pipe open after we exit.
  set +e
  # set -m gives the sweep its own process group, so a timeout kill takes
  # the whole tree — ready-front's gh children included — not just the
  # wrapper shell (orphaned gh processes would otherwise accumulate under
  # repeated GETs).
  set -m
  ( cd "$REPO_ROOT" && exec "$READY_FRONT" ) > "$TMP/rf.out" 2> "$TMP/rf.err" &
  rf_pid=$!
  set +m
  ( sleep "$READY_FRONT_TIMEOUT"; if kill -- -"$rf_pid" 2>/dev/null; then : > "$TMP/rf.timedout"; fi ) > /dev/null 2>&1 &
  wd_pid=$!
  wait "$rf_pid"
  rf_rc=$?
  kill "$wd_pid" 2>/dev/null
  wait "$wd_pid" 2>/dev/null
  kill -- -"$rf_pid" 2>/dev/null
  set -e
  if [ -f "$TMP/rf.timedout" ] && [ "$rf_rc" -ne 0 ]; then
    emit_failed "ready-front.sh timed out after ${READY_FRONT_TIMEOUT}s and was killed (exit $rf_rc); partial output below" ""
  elif [ "$rf_rc" -ne 0 ]; then
    emit_failed "ready-front.sh exited $rf_rc; captured output below" ""
  fi
  emit_pre_file "stdout (the Ready Front)" "$TMP/rf.out"
  emit_pre_file "stderr (the bucket partition)" "$TMP/rf.err"
fi
emit '</div>'

# ------------------------------------------------- section 6: Latest reports
emit '<div class="sec" id="reports">'
emit '<h2>Latest reports</h2>'
emit "<p class=\"muted\">last 3 comments on <a href=\"https://github.com/$REPO/issues/$REPORTS_ISSUE\">issue #$REPORTS_ISSUE</a>, newest first</p>"
# Deliberate set +e island: a failed gh api call renders FAILED in place.
# --paginate walks every page (the endpoint is oldest-first, so without it
# the "latest" reports would go permanently stale at comment 100); each
# page arrives as its own array, so the object stream is reassembled into
# one array for the tail-walk below.
set +e
gh api --paginate "repos/$REPO/issues/$REPORTS_ISSUE/comments?per_page=100" --jq '.[]' 2> "$TMP/comments.err" | jq -s '.' > "$TMP/comments.json"
rep_rc=$?
set -e
if [ "$rep_rc" -ne 0 ]; then
  emit_failed "gh api repos/$REPO/issues/$REPORTS_ISSUE/comments failed (exit $rep_rc)" "$(cat "$TMP/comments.err" 2>/dev/null)"
else
  # Deliberate set +e island: unparseable JSON renders FAILED in place.
  set +e
  rep_n="$(jq -r 'if type == "array" then length else "not-an-array" end' "$TMP/comments.json" 2> "$TMP/comments_jq.err")"
  rep_jq_rc=$?
  set -e
  if [ "$rep_jq_rc" -ne 0 ] || [ -z "$rep_n" ]; then
    emit_failed "parsing the comments JSON failed" "$(cat "$TMP/comments_jq.err" 2>/dev/null)"
  elif [ "$rep_n" = "not-an-array" ]; then
    emit_failed "comments endpoint did not return an array" "$(head -c 400 "$TMP/comments.json" 2>/dev/null)"
  elif [ "$rep_n" -eq 0 ]; then
    emit '<p class="muted">no reports yet</p>'
  else
    # The endpoint returns comments oldest-first; walk the tail backwards.
    idx=$((rep_n - 1))
    shown=0
    while [ "$idx" -ge 0 ] && [ "$shown" -lt 3 ]; do
      c_author="$(jq -r ".[$idx].user.login // \"?\"" "$TMP/comments.json")"
      c_created="$(jq -r ".[$idx].created_at // \"?\"" "$TMP/comments.json")"
      c_url="$(jq -r ".[$idx].html_url // \"\"" "$TMP/comments.json")"
      jq -r ".[$idx].body // \"\"" "$TMP/comments.json" > "$TMP/body.raw"
      # head reads from the file (not a pipe) so a long body cannot SIGPIPE
      # an upstream writer under pipefail.
      head -40 "$TMP/body.raw" | tr -d '\r' > "$TMP/body.txt"
      body_lines="$(wc -l < "$TMP/body.raw" | tr -d ' ')"
      emit '<div class="report">'
      emit "<div class=\"subhead\"><strong>$(esc "$c_author")</strong> &middot; $(esc "${c_created/T/ }") &middot; <a href=\"$(esc "$c_url")\">open comment</a></div>"
      if [ -s "$TMP/body.txt" ]; then
        emit "<pre>$(html_escape < "$TMP/body.txt")</pre>"
      else
        emit '<p class="muted">(empty body)</p>'
      fi
      if [ "$body_lines" -gt 40 ]; then
        emit "<p class=\"muted\">truncated at 40 of $body_lines lines; open the comment for the rest</p>"
      fi
      emit '</div>'
      idx=$((idx - 1))
      shown=$((shown + 1))
    done
  fi
fi
emit '</div>'

# ------------------------------------------------------------------ page foot
emit '<p class="muted">generated by tools/fleet/war-room.sh (issue #279); each section derives independently and fails in place, never silently.</p>'
cat >> "$OUT_TMP" <<'FOOT_HTML'
</body>
</html>
FOOT_HTML

mv -f "$OUT_TMP" "$OUT"
OUT_TMP=""

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "war-room.sh: wrote $OUT with $FAIL_COUNT FAILED section derivation(s)" >&2
  exit 1
fi
echo "war-room.sh: wrote $OUT; every section derived" >&2
exit 0
