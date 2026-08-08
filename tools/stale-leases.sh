#!/usr/bin/env bash
# tools/stale-leases.sh — the Lease staleness report.
#
# docs/harness.md ("Leases") owns the definition: no open PR and no
# commit for 48 hours is stale; reap only refs with no commits absent
# from main; unique commits go to the operator. One honest caveat is in
# the output: an untouched Lease sits at main's tip, so its commit age is
# main's, not its own — the Warden's two-sighting clock (role-warden)
# covers that gap; this file only reports the facts.
#
# Read-only. Output: TSV — issue, ref, age of tip commit, commits ahead
# of main, open PRs, verdict.
set -euo pipefail

REPO=jbgh2/card-game-dsl
STALE_H=48
NOW=$(date +%s)

refs=$(gh api --paginate "repos/$REPO/git/matching-refs/heads/claude/issue-" \
  | jq -s -r 'add // [] | .[].ref | select(test("^refs/heads/claude/issue-[0-9]+$"))')

[ -n "$refs" ] || { echo "no Leases exist"; exit 0; }

while IFS= read -r ref; do
  br=${ref#refs/heads/}
  n=${br#claude/issue-}
  last=$(gh api "repos/$REPO/commits?sha=$br&per_page=1" --jq '.[0].commit.committer.date')
  # Commit dates are UTC (trailing Z); BSD date -j -f reads the pattern in
  # the local zone and takes Z as a literal, so pin TZ=UTC (GNU date in the
  # fallback parses the zone from the string itself).
  last_s=$(TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$last" +%s 2>/dev/null || date -d "$last" +%s)
  age_h=$(( (NOW - last_s) / 3600 ))
  ahead=$(gh api "repos/$REPO/compare/main...$br" --jq '.ahead_by')
  prs=$(gh pr list --repo "$REPO" --head "$br" --state open --json number --jq 'length')
  verdict="fresh"
  if [ "$prs" -eq 0 ] && [ "$age_h" -ge "$STALE_H" ]; then
    if [ "$ahead" -eq 0 ]; then
      verdict="STALE reap-eligible (untouched: tip age is main's — two-sighting clock applies)"
    else
      verdict="STALE flag-operator ($ahead unique commits)"
    fi
  fi
  printf '%s\t%s\tage=%sh\tahead=%s\topen_prs=%s\t%s\n' "$n" "$br" "$age_h" "$ahead" "$prs" "$verdict"
done <<<"$refs"
