#!/usr/bin/env bash
# tools/ci-route.sh — picks the runner for the merge gate's `check` job.
#
# docs/harness.md ("The physical layer") owns the rule: the gate runs on the
# self-hosted pool when the pool will finish it first, and on a GitHub-hosted
# runner when the pool is asleep or full (ADR-0022). The `route` job in
# .github/workflows/ci.yml runs this file and hands its pick to `check`.
#
# The pick, in order:
#   1. A forced lane wins. The repository variable CI_ROUTE is `auto` (or
#      unset), `laptop` or `hosted`; any other value is refused by name.
#   2. The pool is ALIVE when one of its `check` jobs has been running for at
#      most STALE_MINUTES, or when it answered the probe.
#   3. Nothing shows it alive and no probe has been sent: send the probe, a
#      one-step job on the pool (.github/workflows/runner-probe.yml), and
#      decide again on whether it started within PROBE_WAIT_SECONDS. A pool
#      that is asleep or busy does not start it.
#   4. Not alive after a silent probe: hosted.
#   5. Alive: the load is the minutes left on its running `check` jobs, plus
#      LAPTOP_MINUTES for each of its `check` jobs not yet started and for
#      each older run of the workflow still routing. Laptop when the load
#      plus LAPTOP_MINUTES is at most HOSTED_MINUTES; hosted otherwise.
# A gather or probe that fails picks hosted and says why: the hosted lane
# needs nothing from this script to be right.
#
# The two durations are medians of green `check` jobs per lane, re-derived by
# `gh run list --workflow ci.yml --json databaseId` and each run's `check`
# job times; the stale bound sits above the longest green pool job.
#
# Usage: ci-route.sh            live, inside the `route` job; writes `lane`
#                               and `runner` to $GITHUB_OUTPUT.
#        ci-route.sh --decide   reads a facts object on stdin and prints
#                               `<laptop|hosted|probe><TAB><reason>`; the
#                               seam tests/test_ci_route.py drives.
# Needs gh (GH_TOKEN with actions: write) and jq.
set -euo pipefail

LAPTOP_MINUTES=20
HOSTED_MINUTES=55
STALE_MINUTES=45
PROBE_WAIT_SECONDS=60
PROBE_WORKFLOW=runner-probe.yml
PROBE_REF=ci-probe-anchor
POOL_RUNNER='["self-hosted","cardlang"]'
HOSTED_RUNNER='"macos-latest"'

DECIDE='
def pool: (.labels // []) | index("self-hosted") != null;
def gate: [.jobs[] | select(.name == "check")] | first;
def routing: (.jobs | length) == 0 or any(.jobs[]; .name == "route" and .status != "completed");

. as $f
| ($f.force // "") as $force
| if $force == "hosted" then {lane: "hosted", reason: "CI_ROUTE forces the hosted lane"}
  elif $force == "laptop" then {lane: "laptop", reason: "CI_ROUTE forces the laptop"}
  elif $force != "" and $force != "auto" then error("unknown lane")
  else
    [$f.runs[] | select(.id != $f.me)] as $others
    | [$others[] | select(routing | not) | gate | select(. != null and pool)] as $jobs
    | [$jobs[] | select(.status == "in_progress")
       | (($f.now - (.started_at | fromdateiso8601)) / 60)] as $elapsed
    | [$elapsed[] | select(. <= $f.stale_minutes)] as $fresh
    | ([$jobs[] | select(.status != "in_progress" and .status != "completed")] | length) as $waiting
    | ([$others[] | select(.id < $f.me and routing)] | length) as $ahead
    | (($fresh | length) > 0 or $f.probe == "answered") as $alive
    | if ($alive | not) and $f.probe == null then
        {lane: "probe", reason: "nothing shows the laptop awake"}
      elif ($alive | not) then
        {lane: "hosted", reason: "the laptop did not answer the probe"}
      else
        (([$elapsed[] | [$f.laptop_minutes - ., 0] | max] | add // 0)
          + $f.laptop_minutes * ($waiting + $ahead)) as $load
        | ($load + $f.laptop_minutes | round) as $finish
        | (($elapsed | length) + $waiting + $ahead) as $n
        | if $load + $f.laptop_minutes <= $f.hosted_minutes then
            {lane: "laptop",
             reason: "the laptop is awake with \($n) gate job(s) ahead, done in about \($finish) min"}
          else
            {lane: "hosted",
             reason: "\($n) gate job(s) ahead on the laptop, about \($finish) min against \($f.hosted_minutes) hosted"}
          end
      end
  end
| "\(.lane)\t\(.reason)"
'

decide() {
  # stdin: the facts object. stdout: lane, tab, reason.
  local out
  if ! out=$(jq -r "$DECIDE" 2>&1); then
    case "$out" in
      *"unknown lane"*)
        echo "ci-route.sh: CI_ROUTE must be auto, laptop or hosted" >&2
        return 2
        ;;
    esac
    echo "ci-route.sh: the facts did not parse: $out" >&2
    return 1
  fi
  printf '%s\n' "$out"
}

if [ "${1:-}" = "--decide" ]; then
  decide
  exit $?
fi
[ $# -eq 0 ] || { echo "usage: ci-route.sh | ci-route.sh --decide < facts.json" >&2; exit 2; }

REPO=${GITHUB_REPOSITORY:?ci-route.sh runs inside GitHub Actions}
ME=${GITHUB_RUN_ID:?}
WORKFLOW=ci.yml

settle() {
  # $1 lane, $2 reason.
  local runner=$HOSTED_RUNNER
  [ "$1" = laptop ] && runner=$POOL_RUNNER
  {
    echo "lane=$1"
    echo "runner=$runner"
  } >> "$GITHUB_OUTPUT"
  echo "route: $1 -- $2" | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
  exit 0
}

fall_back() {
  echo "::warning title=ci-route::$1; the gate takes the hosted lane"
  settle hosted "$1"
}

gather() {
  # The unfinished runs of this workflow, each with its jobs.
  local runs id
  runs=$(gh api "repos/$REPO/actions/workflows/$WORKFLOW/runs?per_page=100" \
    --jq '[.workflow_runs[] | select(.status != "completed") | .id]') || return 1
  for id in $(jq -r '.[]' <<<"$runs"); do
    gh api "repos/$REPO/actions/runs/$id/jobs?per_page=100" \
      --jq "{id: $id, jobs: [.jobs[] | {name, status, labels, started_at}]}" || return 1
  done | jq -s .
}

facts() {
  # $1 the gathered runs, $2 the probe result as JSON (null or a string).
  jq -n --argjson runs "$1" --argjson probe "$2" --arg force "${CI_ROUTE:-auto}" \
    --argjson me "$ME" --argjson laptop "$LAPTOP_MINUTES" \
    --argjson hosted "$HOSTED_MINUTES" --argjson stale "$STALE_MINUTES" \
    '{force: $force, me: $me, now: now, laptop_minutes: $laptop, hosted_minutes: $hosted,
      stale_minutes: $stale, probe: $probe, runs: $runs}'
}

probe() {
  # Prints `answered` or `silent`. A probe left unanswered is cancelled, so
  # it never runs later against a laptop that has work to do.
  local nonce="$ME.${GITHUB_RUN_ATTEMPT:-1}" deadline found id state
  gh workflow run "$PROBE_WORKFLOW" --repo "$REPO" --ref "$PROBE_REF" -f nonce="$nonce" >&2 || return 1
  deadline=$(( $(date +%s) + PROBE_WAIT_SECONDS ))
  id=""
  while [ "$(date +%s)" -lt "$deadline" ]; do
    sleep 3
    found=$(gh api "repos/$REPO/actions/workflows/$PROBE_WORKFLOW/runs?event=workflow_dispatch&per_page=30" \
      --jq "[.workflow_runs[] | select(.display_title == \"probe $nonce\")] | first // empty | \"\(.id) \(.status) \(.conclusion)\"") || continue
    [ -n "$found" ] || continue
    read -r id state verdict <<<"$found"
    if [ "$state" = in_progress ] || [ "$verdict" = success ]; then
      echo answered
      return 0
    fi
    [ "$state" != completed ] || break
  done
  [ -z "$id" ] || gh api -X POST "repos/$REPO/actions/runs/$id/cancel" >/dev/null 2>&1 || true
  echo silent
}

pick=$(facts '[]' null | decide) || exit $?
lane=${pick%%$'\t'*}
[ "$lane" = probe ] || settle "$lane" "${pick#*$'\t'}"

runs=$(gather) || fall_back "the workflow's runs could not be read"
pick=$(facts "$runs" null | decide) || fall_back "the gathered facts could not be decided"
lane=${pick%%$'\t'*}
[ "$lane" = probe ] || settle "$lane" "${pick#*$'\t'}"

answer=$(probe) || fall_back "the probe could not be sent"
pick=$(facts "$runs" "\"$answer\"" | decide) || fall_back "the probed facts could not be decided"
settle "${pick%%$'\t'*}" "${pick#*$'\t'}"
