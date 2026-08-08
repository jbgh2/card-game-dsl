#!/usr/bin/env bash
# tools/tracker-sweeps.sh — the tracker-hygiene sweeps, one run.
#
# CLAUDE.md ("The tracker") owns the semantics of the first two sections:
# the queries below are its fenced sweeps in executable form — this file
# cites, it never redefines. The third section lists what
# blocked:needs-witness gates, for the judgment the label demands: a
# witness-gated issue whose body names no witness is mislabeled.
#
# Read-only; the Warden (role-warden) acts on what this reports.
# Empty first two sections are the clean state.
set -euo pipefail

REPO=jbgh2/card-game-dsl
LIMIT=200

# The gh --limit flag is a silent cap; refuse to report from a full page.
OPEN=$(gh issue list --repo "$REPO" --state open --limit "$LIMIT" --json number --jq 'length')
if [ "$OPEN" -ge "$LIMIT" ]; then
  echo "capped: $OPEN open issues fill the $LIMIT page — raise LIMIT" >&2
  exit 1
fi

echo "== kindless (clean state: empty) =="
gh issue list --repo "$REPO" --state open --limit "$LIMIT" \
  --json number,title,labels --jq '.[] | select([.labels[].name] | any(. == "bug" or . == "enhancement" or . == "documentation" or . == "tech-debt" or . == "epic") | not) | "\(.number) \(.title)"'

echo "== unordered: no reachability label (clean state: empty) =="
gh issue list --repo "$REPO" --state open --limit "$LIMIT" \
  --json number,title,labels --jq '.[] | select(([.labels[].name] | any(startswith("reachability:")) or any(. == "epic")) | not) | "\(.number) \(.title)"'

echo "== witness-gated: judge that each body NAMES its witness =="
gh issue list --repo "$REPO" --state open --label blocked:needs-witness --limit "$LIMIT" \
  --json number,title --jq '.[] | "\(.number) \(.title)"'
