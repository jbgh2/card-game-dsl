#!/usr/bin/env bash
# tools/tracker-sweeps.sh — the tracker-hygiene sweeps, one run.
#
# CLAUDE.md ("The tracker") owns the semantics of the first two sections:
# the queries below are its fenced sweeps in executable form — this file
# cites, it never redefines. The third section lists what
# blocked:needs-witness gates, for the judgment the label demands: a
# witness-gated issue whose body names no witness is mislabeled. The
# fourth counts the designer-reachable issues filed since the newest
# direction-review verdict that carry no priority tier: a latency the
# direction review clears at its next run (docs/harness.md, "The Ready
# Front"), never a filing defect — a filer does not set tiers.
#
# Read-only; the Warden (role-warden) acts on what this reports.
# Empty first two sections are the clean state.
set -euo pipefail

REPO=jbgh2/card-game-dsl
LIMIT=500

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

# The newest verdict is the newest file in the verdicts' directory; the
# script runs from the repo root, as the Warden's charter has it run.
VERDICTS=docs/superpowers/direction-reviews
NEWEST=$(ls "$VERDICTS" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' | sort | tail -1 | sed 's/\.md$//')
[ -n "$NEWEST" ] || { echo "no verdict file under $VERDICTS" >&2; exit 1; }
# The cutoff is inclusive of the verdict's own date: a same-day arrival the
# review triaged carries a tier and drops out of the filter below; one it
# did not see carries none and is listed, so nothing filed after the
# review is ever silent.
echo "== untriaged on or after the $NEWEST verdict: designer-reachable, no priority tier (a latency, not a defect) =="
gh issue list --repo "$REPO" --state open --limit "$LIMIT" \
  --json number,title,labels,createdAt --jq '.[] | select(.createdAt[0:10] >= "'"$NEWEST"'") | select([.labels[].name] | any(. == "reachability:R1" or . == "reachability:R2")) | select([.labels[].name] | any(startswith("priority:")) | not) | "\(.number) \(.title)"'
